"""Overture Maps na S3 (anonymně): které vydání stahovat a dataset jedné vrstvy.

Overture vydává data každý měsíc a na S3 nechává jen poslední dvě až tři vydání. VYDANI je vyzkoušené s touto
šablonou; když už na S3 není, vezme se nejnovější dostupné (struktura dat se mezi vydáními mění jen výjimečně).
Konkrétní vydání jde vynutit proměnnou IZO_OVERTURE=2026-10-21.0 (seznam: s3://overturemaps-us-west-2/release/).
"""
import os, sys
import pyarrow.dataset as ds, pyarrow.fs as fs

VYDANI = '2026-10-21.0'
KOREN = 'overturemaps-us-west-2/release'
_s3 = _vydani = None


def s3():
    global _s3
    if _s3 is None:
        proxy = os.environ.get('HTTPS_PROXY')
        _s3 = fs.S3FileSystem(anonymous=True, region='us-west-2', **({'proxy_options': proxy} if proxy else {}))
    return _s3


def vydani():
    """VYDANI, nebo nejnovější vydání na S3, když VYDANI už smazali (zjistí se jednou za běh)"""
    global _vydani
    if _vydani: return _vydani
    _vydani = os.environ.get('IZO_OVERTURE') or VYDANI
    if os.environ.get('IZO_OVERTURE'): return _vydani
    try:
        dostupne = sorted(i.base_name for i in s3().get_file_info(fs.FileSelector(KOREN)) if i.type == fs.FileType.Directory)
    except Exception as e:                      # bez seznamu zkusit vyzkoušené vydání (chyba se ukáže až při stahování)
        print(f'Overture: seznam vydání nejde načíst ({e}), zkouším {VYDANI}', file=sys.stderr)
        return _vydani
    if dostupne and VYDANI not in dostupne:
        _vydani = dostupne[-1]
        print(f'Overture: vydání {VYDANI} už na S3 není, beru nejnovější {_vydani}', file=sys.stderr)
    return _vydani


def dataset(theme, typ):
    return ds.dataset(f'{KOREN}/{vydani()}/theme={theme}/type={typ}/', filesystem=s3(), format='parquet')


def zapis(tb, f):
    """parquet přes dočasný soubor: po přerušení (Ctrl-C, výpadek) nezůstane useknutý soubor, který by se příště bral jako hotový"""
    import pyarrow.parquet as pq
    pq.write_table(tb, f + '.tmp'); os.replace(f + '.tmp', f)


def pokryva(stazeno, potreba):
    """True, když obdélník potreba (lon0, lon1, lat0, lat1) leží celý ve stazeno"""
    return stazeno[0] <= potreba[0] and potreba[1] <= stazeno[1] and stazeno[2] <= potreba[2] and potreba[3] <= stazeno[3]


def rozsah(tabulky):
    """obdélník, který dotaz na Overture jistě pokrýval (pro data_all bez bbox.json): dotaz bere prvky, jejichž bbox ho protíná,
    takže jeho západní okraj leží západně od východního okraje každého staženého prvku (a obdobně ostatní strany)"""
    import pyarrow.compute as pc
    b = [t.column('bbox').combine_chunks() for t in tabulky if t.num_rows]
    if not b: return None
    return [min(pc.min(x.field('xmax')).as_py() for x in b), max(pc.max(x.field('xmin')).as_py() for x in b),
            min(pc.min(x.field('ymax')).as_py() for x in b), max(pc.max(x.field('ymin')).as_py() for x in b)]
