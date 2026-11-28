<?php
/**
 * Ukázková konfigurace backend adaptéru hry "Najdeš to?".
 * Zkopírujte jako api/config.php (neverzuje se v Gitu).
 */
return [
    'secret_key'   => 'ZMENTE_NA_DLOUHY_NAHODNY_RETEZEC',
    'admin_key'    => 'ZMENTE_NA_SILNE_ADMIN_HESLO',
    'targets_file' => __DIR__ . '/../../site_server/server_data/najdi_to.targets.json',
    'db_path'      => __DIR__ . '/../../site_server/server_data/najdi_to.sqlite',
    // true jen za Cloudflare nebo vlastní reverse proxy, která hlavičky CF-Connecting-IP / X-Forwarded-For sama nastavuje
    // a přes kterou jediná vede cesta k serveru; jinak si je hráč podvrhne a obejde 1 soutěžní pokus
    'trust_proxy'  => false,
];
