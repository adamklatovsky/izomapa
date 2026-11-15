<?php
/**
 * Ukázková konfigurace referenčního PHP adaptéru.
 * Zkopírujte jako config.php vedle skriptu a nikdy necommitujte do Gitu.
 */
return [
    'secret_key'   => 'ZMENTE_NA_DLOUHY_NAHODNY_RETEZEC',
    'targets_file' => __DIR__ . '/../../site_server/server_data/vzor_doplnku.targets.json',
    'db_path'      => __DIR__ . '/data/vzor_doplnku.sqlite',
];
