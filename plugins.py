"""Univerzální zavaděč doplňků (Plugin Architecture) pro izomapu."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any, Callable


_PRIVATE_CONFIG_KEYS = {
    'server_data_out', 'secret_key', 'admin_key', 'salt', 'targets_file',
    'profanity_extra_words', 'profanity_allow_words',
}
_PROFANITY_FILE = Path(__file__).resolve().with_name('profanity_words.json')
_LEET_MAP = str.maketrans({'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a', '$': 's', '!': 'i'})
_FALLBACK_PROFANITY = {
    'exact_words': ['vul', 'vole', 'pica', 'pico', 'picu', 'kunda', 'debil', 'kreten', 'idiot', 'blbec', 'hajzl', 'chuj', 'fuck', 'shit', 'bitch', 'asshole'],
    'prefixes': ['kurv', 'curak', 'kokot', 'zmrd', 'mrda', 'jebat', 'jebu', 'prdel', 'srack', 'srat', 'sukat', 'buzer'],
    'compact_phrases': ['kurv', 'curak', 'kokot', 'zmrd', 'prdel', 'srack', 'buzerant', 'fuck'],
}


def _strip_accents(text: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFKD', text) if not unicodedata.combining(ch))


def normalize_profanity_text(text: str, leet: bool = False) -> str:
    """Převede text na malá ASCII písmena; volitelně nahradí běžné leetspeak znaky."""
    out = _strip_accents(str(text or '').lower())
    if leet:
        out = out.translate(_LEET_MAP)
    return out


def _collapse_repeats(token: str, max_repeat: int = 1) -> str:
    return re.sub(r'(.)\1{' + str(max_repeat) + r',}', r'\1' * max_repeat, token)


def load_profanity_words(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Načte sdílený slovník sprostých slov a sloučí ho s volitelnou konfigurací doplňku."""
    base = json.loads(_PROFANITY_FILE.read_text(encoding='utf-8')) if _PROFANITY_FILE.is_file() else dict(_FALLBACK_PROFANITY)
    exact = {normalize_profanity_text(w) for w in base.get('exact_words', []) if str(w).strip()}
    prefixes = {normalize_profanity_text(w) for w in base.get('prefixes', []) if str(w).strip()}
    compact = {normalize_profanity_text(w) for w in base.get('compact_phrases', []) if str(w).strip()}

    cfg = cfg or {}
    allow = {normalize_profanity_text(w) for w in cfg.get('profanity_allow_words', []) if str(w).strip()}
    for extra in cfg.get('profanity_extra_words', []):
        norm = normalize_profanity_text(str(extra)).strip()
        if norm:
            exact.add(norm)
            if len(norm) >= 4:
                prefixes.add(norm)

    return {
        'enabled': bool(cfg.get('profanity_filter', True)),
        'exact_words': sorted(exact - allow),
        'prefixes': sorted(prefixes - allow),
        'compact_phrases': sorted(compact - allow),
        'allow_words': sorted(allow),
    }


def contains_profanity(text: str, cfg: dict[str, Any] | None = None) -> bool:
    """Vrátí True, pokud text (přezdívka) obsahuje nepovolené slovo (vč. diakritiky, teček a leetspeaku)."""
    rules = load_profanity_words(cfg)
    if not rules['enabled']:
        return False

    exact = set(rules['exact_words'])
    prefixes = tuple(rules['prefixes'])
    compact_phrases = tuple(rules['compact_phrases'])
    allow = set(rules['allow_words'])

    for leet in (False, True):
        norm = normalize_profanity_text(text, leet=leet)
        # Slepí rozsekaná písmena typu "k.u.r.v.a" nebo "p i c a" do jednoho tokenu
        merged = re.sub(r'(?<![a-z0-9])(?:[a-z0-9][\s._*+-]+){2,}[a-z0-9](?![a-z0-9])', lambda m: re.sub(r'[^a-z0-9]', '', m.group(0)), norm)
        tokens = re.findall(r'[a-z0-9]+', merged)
        for tok in tokens:
            if tok in allow:
                continue
            for cand in (tok, _collapse_repeats(tok, 1)):
                if cand in allow:
                    continue
                if cand in exact or (prefixes and cand.startswith(prefixes)):
                    return True
        compact = re.sub(r'[^a-z0-9]+', '', norm)
        for cand_compact in (compact, _collapse_repeats(compact, 1)):
            if any(phrase in cand_compact for phrase in compact_phrases):
                return True
    return False


def censor_profanity(text: str, cfg: dict[str, Any] | None = None, replacement: str = '***') -> str:
    """Nahradí nevhodnou přezdívku zástupným textem pro defenzivní zobrazení v žebříčku."""
    return replacement if contains_profanity(text, cfg) else text


def _normalize_entries(raw: Any) -> dict[str, dict[str, Any]]:
    """Normalizuje konfiguraci doplňků (seznam názvů nebo slovník) na {plugin_id: dict}."""
    out: dict[str, dict[str, Any]] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                out[item.strip()] = {'enabled': True}
    elif isinstance(raw, dict):
        for pid, val in raw.items():
            if not isinstance(pid, str) or not pid.strip():
                continue
            if isinstance(val, bool):
                out[pid.strip()] = {'enabled': val}
            elif isinstance(val, dict):
                out[pid.strip()] = dict(val)
    return out


def _installed_plugin_ids(assets_dir: Path, plugins_dir: Path) -> list[str]:
    """Vrátí seznam ID nainstalovaných doplňků podle manifest.json."""
    found: list[str] = []
    seen: set[str] = set()
    for base in (plugins_dir, assets_dir / 'doplnky'):
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            if entry.is_dir() and (entry / 'manifest.json').is_file() and entry.name not in seen:
                seen.add(entry.name)
                found.append(entry.name)
    return found


def resolve_plugin_dir(plugin_id: str, assets_dir: Path, plugins_dir: Path) -> Path | None:
    """Najde složku doplňku (lokální assets/doplnky/<id> má přednost před doplnky/<id>)."""
    local_dir = assets_dir / 'doplnky' / plugin_id
    if local_dir.is_dir():
        return local_dir
    shared_dir = plugins_dir / plugin_id
    if shared_dir.is_dir():
        return shared_dir
    return None


def discover_plugin_configs(mesto: dict[str, Any], assets_dir: Path, plugins_dir: Path) -> dict[str, dict[str, Any]]:
    """Určí aktivní doplňky v pořadí: mesto.json -> assets/doplnky.json -> auto-discovery."""
    merged = _normalize_entries(mesto.get('doplnky'))
    cfg_path = assets_dir / 'doplnky.json'

    if cfg_path.is_file():
        file_entries = _normalize_entries(json.loads(cfg_path.read_text(encoding='utf-8')))
        for pid, cfg in file_entries.items():
            merged[pid] = {**merged.get(pid, {}), **cfg}
    else:
        for pid in _installed_plugin_ids(assets_dir, plugins_dir):
            if (assets_dir / f'{pid}.json').is_file():
                existing = merged.get(pid, {})
                if existing.get('enabled') is False:
                    continue
                merged[pid] = {'enabled': True, **existing}

    return {pid: cfg for pid, cfg in merged.items() if cfg.get('enabled', True) is True}


def ensure_server_data_protection(server_root: Path) -> Path:
    """Vytvoří site_server/server_data/, README.md a .htaccess proti přímému čtení."""
    server_data_dir = server_root / 'server_data'
    server_data_dir.mkdir(parents=True, exist_ok=True)

    readme_path = server_root / 'README.md'
    if not readme_path.exists():
        readme_path.write_text(
            '# Soukromá serverová data doplňků (`site_server/`)\n\n'
            'Tato složka obsahuje neveřejná data pro backendové adaptéry doplňků '
            '(např. přesné cílové souřadnice v `server_data/*.targets.json`).\n\n'
            '## Bezpečnostní pravidlo\n'
            '- Složka `site_server/` **nepatří do veřejného webrootu** (nikdy ji nenahrávejte do `site/`).\n'
            '- Na serveru ji umístěte mimo kořen webu (`DocumentRoot`) nebo zablokujte přístup z HTTP '
            '(soubor `server_data/.htaccess` je vygenerován automaticky pro Apache).\n',
            encoding='utf-8',
        )

    htaccess_path = server_data_dir / '.htaccess'
    if not htaccess_path.exists():
        htaccess_path.write_text('Require all denied\nDeny from all\n', encoding='utf-8')

    return server_data_dir


def _load_hook(hook_path: Path, plugin_id: str) -> Any:
    """Dynamicky načte Python modul overlay_hook.py bez znečištění sys.modules."""
    spec = importlib.util.spec_from_file_location(f'_izomapa_plugin_{plugin_id}', str(hook_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Nelze načíst hook doplňku {plugin_id}: {hook_path}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _copy_plugin_assets(plugin_id: str, plugin_dir: Path, manifest: dict[str, Any], site_dir: Path) -> tuple[list[str], list[str]]:
    """Zkopíruje JS a CSS soubory doplňku do site/doplnky/<plugin_id>/ a vrátí relativní URL."""
    raw_scripts = manifest.get('scripts') or manifest.get('js') or [f'{plugin_id}.js']
    raw_styles = manifest.get('styles') or manifest.get('css') or [f'{plugin_id}.css']
    dest_dir = site_dir / 'doplnky' / plugin_id

    def _copy_list(items: list[str]) -> list[str]:
        urls: list[str] = []
        for rel in items:
            src = plugin_dir / rel
            if not src.is_file():
                continue
            target = dest_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            urls.append(f'doplnky/{plugin_id}/{rel.lstrip("./")}')
        return urls

    return _copy_list(list(raw_scripts)), _copy_list(list(raw_styles))


def load_and_run_plugins(
    mesto: dict[str, Any],
    cam: dict[str, Any],
    project_xy: Callable[..., list[float] | tuple[float, float]],
    assets_dir: str | Path = 'assets',
    site_dir: str | Path = 'site',
    build_dir: str | Path = 'build',
    server_root: str | Path = 'site_server',
    plugins_dir: str | Path = 'doplnky',
) -> dict[str, dict[str, Any]]:
    """Spustí aktivní build-time hooky doplňků a vrátí sekci 'doplnky' pro site/overlay.json."""
    assets_p = Path(assets_dir)
    site_p = Path(site_dir)
    build_p = Path(build_dir)
    server_p = Path(server_root)
    plugins_p = Path(plugins_dir)

    active = discover_plugin_configs(mesto, assets_p, plugins_p)
    if not active:
        return {}

    result: dict[str, dict[str, Any]] = {}
    for plugin_id, user_cfg in active.items():
        plugin_dir = resolve_plugin_dir(plugin_id, assets_p, plugins_p)
        if plugin_dir is None:
            print(f'Varování: složka doplňku "{plugin_id}" nebyla nalezena.')
            continue

        manifest_path = plugin_dir / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else {}
        merged_cfg: dict[str, Any] = {
            'mode': manifest.get('default_mode', 'client'),
            'profanity_filter': True,
            **dict(manifest.get('defaults') or {}),
            **user_cfg,
        }
        mode = merged_cfg.get('mode', 'client')
        profanity_cfg = load_profanity_words(merged_cfg)

        server_data_dir = server_p / 'server_data'
        if mode == 'server':
            server_data_dir = ensure_server_data_protection(server_p)
            merged_cfg.setdefault('server_data_out', str(server_data_dir / f'{plugin_id}.targets.json'))
            (server_data_dir / 'profanity.json').write_text(
                json.dumps(profanity_cfg, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )

        ctx: dict[str, Any] = {
            'plugin_id': plugin_id,
            'plugin_config': merged_cfg,
            'mesto': mesto,
            'cam': cam,
            'project_xy': project_xy,
            'assets_dir': assets_p,
            'plugin_dir': plugin_dir,
            'site_dir': site_p,
            'build_dir': build_p,
            'server_root': server_p,
            'server_data_dir': server_data_dir,
            'profanity_config': profanity_cfg,
            'contains_profanity': contains_profanity,
        }

        hook_rel = manifest.get('hook', 'overlay_hook.py')
        hook_path = plugin_dir / hook_rel
        public_data: Any = {}
        if hook_path.is_file():
            mod = _load_hook(hook_path, plugin_id)
            if hasattr(mod, 'build_overlay'):
                hook_out = mod.build_overlay(ctx)
                if hook_out is False or hook_out is None:
                    continue
                if isinstance(hook_out, dict):
                    public_data = hook_out

        scripts, styles = _copy_plugin_assets(plugin_id, plugin_dir, manifest, site_p)
        public_cfg = {k: v for k, v in merged_cfg.items() if k not in _PRIVATE_CONFIG_KEYS}
        result[plugin_id] = {
            'id': plugin_id,
            'config': public_cfg,
            'scripts': scripts,
            'styles': styles,
            'data': public_data,
        }

    return result
