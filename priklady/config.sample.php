<?php
/**
 * Ukázka volitelné lokální konfigurace pro api/najdi_to.php.
 *
 * Pro použití na serveru zkopírujte tento soubor jako config.php do složky api/
 * a nastavte vlastní tajné heslo pro zobrazení auditu (admin_key).
 * Soubor config.php je ignorován v Gitu a nikdy se nenahrává do veřejného repozitáře.
 */

return [
    // Tajný klíč pro přístup k internímu auditnímu logu (IP adresy, pokusy, časy)
    // Přístup: https://tvoje-domena.cz/api/najdi_to.php?audit=1&key=SEM_DEJ_HESLO
    'admin_key' => 'zvol_si_vlastni_tajne_heslo',

    // Volitelná vlastní sůl pro hashování IP adres
    'salt' => 'moje_tajna_sul_123',
];
