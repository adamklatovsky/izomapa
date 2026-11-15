<?php
/**
 * Referenční jazykově nezávislý PHP adaptér pro systém doplňků Izomapy (SQLite + JSON fallback).
 * Implementuje bezstavové HMAC-SHA256 tickety (start, verify, finish, leaderboard)
 * a týdenně rotovaný 12znakový GDPR audit_hash bez ukládání surové IP adresy.
 */
declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    header('Content-Type: application/json; charset=utf-8');
    header('Access-Control-Allow-Origin: *');
    header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type');
    if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') {
        http_response_code(204);
        exit;
    }
}

function vzor_clip(string $s, int $max): string {
    return function_exists('mb_substr') ? mb_substr($s, 0, $max, 'UTF-8') : substr($s, 0, $max);
}

function vzor_b64url_encode(string $raw): string {
    return rtrim(strtr(base64_encode($raw), '+/', '-_'), '=');
}

function vzor_b64url_decode(string $text): string {
    $pad = strlen($text) % 4;
    if ($pad > 0) $text .= str_repeat('=', 4 - $pad);
    $decoded = base64_decode(strtr($text, '-_', '+/'), true);
    if ($decoded === false) throw new InvalidArgumentException('Neplatné base64url kódování');
    return $decoded;
}

function vzor_create_ticket(array $payload, string $secretKey): string {
    $encoded = vzor_b64url_encode(json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    return $encoded . '.' . hash_hmac('sha256', $encoded, $secretKey);
}

function vzor_verify_ticket(string $ticket, string $secretKey): array {
    $parts = explode('.', $ticket, 2);
    if (count($parts) !== 2) throw new InvalidArgumentException('Neplatný formát ticketu');
    [$encoded, $sig] = $parts;
    $expected = hash_hmac('sha256', $encoded, $secretKey);
    if (!hash_equals($expected, $sig)) throw new InvalidArgumentException('Neplatný HMAC podpis ticketu');
    $payload = json_decode(vzor_b64url_decode($encoded), true);
    if (!is_array($payload)) throw new InvalidArgumentException('Neplatný payload ticketu');
    return $payload;
}

function vzor_audit_hash(string $clientIp, string $secretKey, ?int $timestampSec = null): string {
    $ts = $timestampSec ?? time();
    return substr(hash_hmac('sha256', $clientIp . '|' . gmdate('o-W', $ts), $secretKey), 0, 12);
}

function vzor_client_ip(): string {
    if (!empty($_SERVER['HTTP_CF_CONNECTING_IP'])) return trim((string)$_SERVER['HTTP_CF_CONNECTING_IP']);
    if (!empty($_SERVER['HTTP_X_FORWARDED_FOR'])) return trim(explode(',', (string)$_SERVER['HTTP_X_FORWARDED_FOR'])[0]);
    return trim((string)($_SERVER['REMOTE_ADDR'] ?? '127.0.0.1'));
}

function vzor_point_in_polygon(float $x, float $y, array $pts): bool {
    $inside = false;
    $n = count($pts);
    for ($i = 0, $j = $n - 1; $i < $n; $j = $i++) {
        $xi = (float)$pts[$i][0]; $yi = (float)$pts[$i][1];
        $xj = (float)$pts[$j][0]; $yj = (float)$pts[$j][1];
        if ((($yi > $y) !== ($yj > $y)) && ($x < ($xj - $xi) * ($y - $yi) / ($yj - $yi) + $xi)) $inside = !$inside;
    }
    return $inside;
}

function vzor_match_question(array $q, float $x, float $y): ?array {
    $rPx = (float)($q['radius_px'] ?? 175.0);
    if (isset($q['xy']) && is_array($q['xy']) && count($q['xy']) >= 2) {
        if (hypot($x - (float)$q['xy'][0], $y - (float)$q['xy'][1]) <= $rPx) {
            return ['x' => (float)$q['xy'][0], 'y' => (float)$q['xy'][1]];
        }
    }
    foreach ($q['targets'] ?? [] as $t) {
        $type = $t['type'] ?? '';
        if ($type === 'point' && isset($t['xy']) && hypot($x - (float)$t['xy'][0], $y - (float)$t['xy'][1]) <= (float)($t['radius_px'] ?? $rPx)) {
            return ['x' => (float)$t['xy'][0], 'y' => (float)$t['xy'][1]];
        }
        if ($type === 'polygon' && !empty($t['points']) && count($t['points']) >= 3 && vzor_point_in_polygon($x, $y, $t['points'])) {
            $cx = array_sum(array_column($t['points'], 0)) / count($t['points']);
            $cy = array_sum(array_column($t['points'], 1)) / count($t['points']);
            return ['x' => round($cx, 1), 'y' => round($cy, 1)];
        }
    }
    return null;
}

function vzor_open_store(string $dbPath): PDO|string {
    if (class_exists('PDO') && in_array('sqlite', PDO::getAvailableDrivers(), true)) {
        $pdo = new PDO('sqlite:' . $dbPath);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->exec("
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                nickname TEXT NOT NULL,
                total_time_ms INTEGER NOT NULL,
                difficulty TEXT NOT NULL,
                season TEXT NOT NULL,
                certificate_id TEXT NOT NULL,
                audit_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_scores_time ON scores(total_time_ms);
        ");
        return $pdo;
    }
    return $dbPath . '.json';
}

function vzor_store_insert(PDO|string $store, array $entry): int {
    if ($store instanceof PDO) {
        $stmt = $store->prepare('INSERT INTO scores (nickname, total_time_ms, difficulty, season, certificate_id, audit_hash) VALUES (?, ?, ?, ?, ?, ?)');
        $stmt->execute([$entry['nickname'], $entry['totalTimeMs'], $entry['difficulty'], $entry['season'], $entry['certificateId'], $entry['auditHash']]);
        $rankStmt = $store->prepare('SELECT COUNT(*) FROM scores WHERE total_time_ms < ?');
        $rankStmt->execute([$entry['totalTimeMs']]);
        return (int)$rankStmt->fetchColumn() + 1;
    }
    $fp = fopen($store, 'c+');
    flock($fp, LOCK_EX);
    $raw = stream_get_contents($fp);
    $rows = $raw ? (json_decode($raw, true) ?: []) : [];
    $rows[] = $entry;
    ftruncate($fp, 0);
    rewind($fp);
    fwrite($fp, json_encode($rows, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    flock($fp, LOCK_UN);
    fclose($fp);
    $faster = count(array_filter($rows, static fn($r) => (int)$r['totalTimeMs'] < (int)$entry['totalTimeMs']));
    return $faster + 1;
}

function vzor_store_leaderboard(PDO|string $store): array {
    if ($store instanceof PDO) {
        return $store->query('SELECT nickname, total_time_ms AS totalTimeMs, difficulty, season, certificate_id AS certificateId, created_at AS createdAt FROM scores ORDER BY total_time_ms ASC, created_at ASC LIMIT 20')->fetchAll(PDO::FETCH_ASSOC);
    }
    if (!is_file($store)) return [];
    $rows = json_decode((string)file_get_contents($store), true) ?: [];
    usort($rows, static fn($a, $b) => ((int)$a['totalTimeMs'] <=> (int)$b['totalTimeMs']) ?: strcmp((string)$a['createdAt'], (string)$b['createdAt']));
    return array_map(static fn($r) => [
        'nickname'      => $r['nickname'],
        'totalTimeMs'   => $r['totalTimeMs'],
        'difficulty'    => $r['difficulty'],
        'season'        => $r['season'],
        'certificateId' => $r['certificateId'],
        'createdAt'     => $r['createdAt'],
    ], array_slice($rows, 0, 20));
}

function vzor_handle_request(array $data, array $targetsData, PDO|string $dbPathOrPdo, string $secretKey, string $clientIp, ?int $nowMs = null): array {
    $ts = $nowMs ?? (int)round(microtime(true) * 1000);
    $action = (string)($data['action'] ?? '');

    $findLevel = static function ($lvlId) use ($targetsData): ?array {
        foreach ($targetsData['levels'] ?? [] as $lvl) {
            if ((string)($lvl['lvl'] ?? '') === (string)$lvlId) return $lvl;
        }
        return null;
    };

    if ($action === 'start') {
        $lvl = $findLevel($data['levelId'] ?? '');
        if ($lvl === null) return [404, ['error' => 'unknown_level', 'message' => 'Úroveň neexistuje']];
        $qs = $lvl['questions'] ?? [];
        $order = count($qs) > 0 ? range(0, count($qs) - 1) : [];
        shuffle($order);
        $payload = [
            'lvl'    => (string)$lvl['lvl'],
            'diff'   => vzor_clip((string)($data['difficulty'] ?? 'easy'), 32),
            'season' => vzor_clip((string)($data['season'] ?? 'summer'), 16),
            'ord'    => $order,
            'step'   => 0,
            'miss'   => 0,
            't0'     => $ts,
            'tl'     => $ts,
            'done'   => false,
            'el'     => 0,
        ];
        $qIds = array_map(static fn($i) => $qs[$i]['id'] ?? '', $order);
        return [200, ['order' => $order, 'questionIds' => $qIds, 'ticket' => vzor_create_ticket($payload, $secretKey)]];
    }

    if ($action === 'verify') {
        try {
            $payload = vzor_verify_ticket((string)($data['ticket'] ?? ''), $secretKey);
        } catch (Throwable $e) {
            return [403, ['error' => 'invalid_ticket', 'message' => $e->getMessage()]];
        }
        if (!empty($payload['done'])) return [400, ['error' => 'already_done', 'message' => 'Úroveň je již dokončená']];
        if ($ts - (int)($payload['tl'] ?? 0) < 300) return [429, ['error' => 'rate_limit', 'message' => 'Příliš rychlé klikání']];
        $lvl = $findLevel($payload['lvl'] ?? '');
        if ($lvl === null) return [404, ['error' => 'unknown_level', 'message' => 'Úroveň neexistuje']];
        $qs = $lvl['questions'] ?? [];
        $ord = $payload['ord'] ?? [];
        $step = (int)($payload['step'] ?? 0);
        if ($step < 0 || $step >= count($ord)) return [400, ['error' => 'invalid_step', 'message' => 'Neplatný krok v ticketu']];
        $q = $qs[$ord[$step]];
        $hitPt = vzor_match_question($q, (float)($data['x'] ?? -1e9), (float)($data['y'] ?? -1e9));
        $payload['tl'] = $ts;

        if ($hitPt === null) {
            $payload['miss'] = (int)($payload['miss'] ?? 0) + 1;
            return [200, ['hit' => false, 'completed' => false, 'ticket' => vzor_create_ticket($payload, $secretKey)]];
        }

        $step++;
        $payload['step'] = $step;
        $elapsed = max(1, $ts - (int)($payload['t0'] ?? $ts));
        if ($step >= count($ord)) {
            $payload['done'] = true;
            $payload['el'] = $elapsed;
        }
        return [200, [
            'hit'        => true,
            'completed'  => (bool)$payload['done'],
            'elapsedMs'  => $elapsed,
            'targetHint' => $hitPt,
            'answer'     => $q['answer'] ?? '',
            'ticket'     => vzor_create_ticket($payload, $secretKey),
        ]];
    }

    $store = $dbPathOrPdo instanceof PDO ? $dbPathOrPdo : vzor_open_store($dbPathOrPdo);

    if ($action === 'finish') {
        $tickets = $data['tickets'] ?? null;
        if (!is_array($tickets) || empty($tickets)) return [400, ['error' => 'missing_tickets', 'message' => 'Chybí tickety úrovní']];
        $required = array_map(static fn($l) => (string)$l['lvl'], $targetsData['levels'] ?? []);
        $verified = [];
        foreach ($tickets as $t) {
            try {
                $p = vzor_verify_ticket((string)$t, $secretKey);
            } catch (Throwable $e) {
                return [403, ['error' => 'invalid_ticket', 'message' => $e->getMessage()]];
            }
            if (empty($p['done'])) return [400, ['error' => 'incomplete_level', 'message' => 'Některá úroveň není dokončená']];
            $lid = (string)($p['lvl'] ?? '');
            if (isset($verified[$lid])) return [400, ['error' => 'duplicate_level', 'message' => 'Duplicitní úroveň v ticketech']];
            $verified[$lid] = $p;
        }
        $reqSet = array_map('strval', $required); sort($reqSet);
        $gotSet = array_map('strval', array_keys($verified)); sort($gotSet);
        if ($reqSet !== $gotSet) return [400, ['error' => 'missing_levels', 'message' => 'Nejsou dokončeny všechny povinné úrovně']];

        $totalMs = 0;
        foreach ($verified as $p) $totalMs += max(1, (int)($p['el'] ?? 0));
        $lastP = $verified[$required[count($required) - 1]];
        $nickname = trim((string)($data['nickname'] ?? ''));
        if ($nickname === '') $nickname = 'Anonymní hledač';
        $nickname = vzor_clip($nickname, 50);
        $auditHash = vzor_audit_hash($clientIp, $secretKey, intdiv($ts, 1000));
        $certId = strtoupper(substr(hash_hmac('sha256', "{$nickname}:{$totalMs}:{$auditHash}:{$ts}", $secretKey), 0, 6));

        $rank = vzor_store_insert($store, [
            'nickname'      => $nickname,
            'totalTimeMs'   => $totalMs,
            'difficulty'    => (string)($lastP['diff'] ?? 'easy'),
            'season'        => (string)($lastP['season'] ?? 'summer'),
            'certificateId' => $certId,
            'auditHash'     => $auditHash,
            'createdAt'     => gmdate('Y-m-d H:i:s', intdiv($ts, 1000)),
        ]);

        return [200, ['saved' => true, 'totalTimeMs' => $totalMs, 'rank' => $rank, 'certificateId' => $certId]];
    }

    if ($action === 'leaderboard') {
        return [200, ['entries' => vzor_store_leaderboard($store)]];
    }

    return [400, ['error' => 'unknown_action', 'message' => 'Neznámá akce']];
}

if (PHP_SAPI !== 'cli' || realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    $cfgFile = __DIR__ . '/config.php';
    $cfg = is_file($cfgFile) ? (require $cfgFile) : [];
    $secretKey = (string)(getenv('IZOMAPA_PLUGIN_SECRET') ?: ($cfg['secret_key'] ?? ''));
    $targetsFile = (string)(getenv('IZOMAPA_TARGETS_FILE') ?: ($cfg['targets_file'] ?? (__DIR__ . '/../../site_server/server_data/vzor_doplnku.targets.json')));
    $dbPath = (string)(getenv('IZOMAPA_DB_PATH') ?: ($cfg['db_path'] ?? (__DIR__ . '/data/vzor_doplnku.sqlite')));

    if ($secretKey === '' || $secretKey === 'ZMENTE_NA_DLOUHY_NAHODNY_RETEZEC') {
        http_response_code(500);
        echo json_encode(['error' => 'missing_secret', 'message' => 'Nastavte secret_key v config.php nebo IZOMAPA_PLUGIN_SECRET']);
        exit;
    }
    if (!is_file($targetsFile)) {
        http_response_code(500);
        echo json_encode(['error' => 'missing_targets', 'message' => 'Soubor targets.json nebyl nalezen']);
        exit;
    }
    if (!is_dir(dirname($dbPath))) @mkdir(dirname($dbPath), 0775, true);

    $targetsData = json_decode((string)file_get_contents($targetsFile), true);
    $method = $_SERVER['REQUEST_METHOD'] ?? (PHP_SAPI === 'cli' ? 'POST' : 'GET');
    $input = ($method === 'GET')
        ? ['action' => $_GET['action'] ?? 'leaderboard']
        : (json_decode((string)file_get_contents(PHP_SAPI === 'cli' ? 'php://stdin' : 'php://input'), true) ?: []);

    [$code, $resp] = vzor_handle_request($input, $targetsData, $dbPath, $secretKey, vzor_client_ip());
    if (PHP_SAPI !== 'cli') http_response_code($code);
    echo json_encode($resp, JSON_UNESCAPED_UNICODE);
}
