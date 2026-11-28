# les podle ortofota ČÚZK: stáhne letecké snímky celé mapy po 2 m/px a z nich masku korun stromů
# -> build/orto/ (dlaždice), build/orto_cele.jpg, build/les_maska.png + .json (prep.py: kde není koruna, je louka a žádné stromy)
# spouštět z kořene repa: python nastroje/les.py   (stahuje se jednou, ~1 min na čtverec)
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, geo
from nastroje.orto import ortofoto
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
D = 'build/orto/'; os.makedirs(D, exist_ok=True)
M = 2.0
X0, Y0, X1, Y1 = geo.extent(geo.MARGIN + 20)
W, H = int((X1 - X0) / M), int((Y1 - Y0) / M); T = 1500
big = Image.new('RGB', (W, H))
for ty in range(0, H, T):
    for tx in range(0, W, T):
        w, h = min(T, W - tx), min(T, H - ty)
        lo0, la1 = geo.to_lonlat(X0 + tx * M, Y1 - ty * M); lo1, la0 = geo.to_lonlat(X0 + (tx + w) * M, Y1 - (ty + h) * M)
        f = f'{D}{round(X0 + tx * M)}_{round(Y1 - ty * M)}_{w}x{h}.jpg'   # podle polohy: po změně rozsahu mapy se nevezme stará dlaždice
        if not ortofoto(f, 'https://ags.cuzk.gov.cz/arcgis1/services/ORTOFOTO/MapServer/WMSServer?SERVICE=WMS&VERSION=1.3.0'
                        f'&REQUEST=GetMap&LAYERS=0&STYLES=&CRS=EPSG:4326&BBOX={la0},{lo0},{la1},{lo1}&WIDTH={w}&HEIGHT={h}&FORMAT=image/jpeg'):
            sys.exit(f'ortofoto se nestáhlo (ČÚZK WMS nedostupná nebo vrátila chybu): {f}, zkus to později')
        big.paste(Image.open(f).convert('RGB'), (tx, ty))
        print('ortofoto', tx, ty, flush=True)
big.save('build/orto_cele.jpg', quality=85)
a = np.asarray(big).astype(np.int16); r, g, b = a[..., 0], a[..., 1], a[..., 2]; L = a.mean(2)
canopy = (g >= r - 4) & (g >= b - 8) & (L < 82)                 # koruny: tmavě zelené; louky a pole jsou světlejší


def box(x, k):
    p = np.pad(x.astype(np.float32), k + 1, mode='edge'); c = p.cumsum(0).cumsum(1); n = 2 * k + 1
    return (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n])[:x.shape[0], :x.shape[1]] / n / n


def koruny(rgb, veg=None, vse=None):
    """přísnější maska korun (mesto.json "les_zrnitost": true): rgb ortofoto po 2 m, veg/vse volitelně počty bodů laseru (třída 5 / všechny) na stejné mřížce"""
    from scipy import ndimage as nd
    avg = lambda x, k: nd.uniform_filter(x.astype(np.float32), 2 * k + 1, mode='nearest')   # box() po cumsum ve float32 na jas nestačí přesností
    a = rgb.astype(np.float32); r, g, b = a[..., 0], a[..., 1], a[..., 2]; L = a.mean(2)
    q = (g - r) / (L + 10); y = (g - b) / (L + 10)              # zelenost a žlutost (louka je žlutější než les)
    hf = avg(np.abs(L - avg(L, 1)), 2)                            # zrnitost: koruny jsou zrnité, asfalt, pole, louka a voda hladké
    t = np.clip(0.06 * (L - 45), 0.8, None) * np.where(y > 0.15, 2.0, 1.0)   # světlejší a žlutější plocha potřebuje víc zrnitosti
    lv = np.zeros(L.shape, bool)
    if veg is not None:                                           # laser vidí vegetaci: stačí polovina zrnitosti a i šedá barva (borovice)
        n = avg(vse, 1); lv = (n > 0) & (avg(veg, 1) >= 0.5 * n); t = np.where(lv, t * 0.5, t)
    canopy = (L < 92) & (g >= b - 8) & (q > np.where(lv, 0.0, 0.06)) & (hf > t)   # modrá = voda
    m = avg(canopy, 2) > 0.4                                     # vyhladit šum (stíny, mezery mezi korunami)
    cut = ((L > 88) & (q < 0.15)) | (L > 100)                     # světlé šedé: cesta, trať, štěrk
    lab, nl = nd.label(cut, np.ones((3, 3))); m &= ~np.r_[False, nd.sum(cut, lab, range(1, nl + 1)) >= 10][lab]   # souvislý pás vyhlazení nezaplní
    lab, nl = nd.label(~m)
    return m | np.r_[False, nd.sum(~m, lab, range(1, nl + 1)) <= 10][lab]   # díry do 40 m² v lese zaplnit


def laser_vegetace(W, H):
    """počty bodů laseru ČÚZK (build/dmp/*.laz) na mřížce masky: třída 5 = vegetace a všechny body; bez laseru (None, None)"""
    import glob, laspy
    from pyproj import Transformer
    fs = sorted(glob.glob('build/dmp/*.laz'))
    if not fs: return None, None
    T = Transformer.from_crs(5514, 4326, always_xy=True)
    veg = np.zeros((H, W), np.uint16); vse = np.zeros((H, W), np.uint16)
    for f in fs:
        l = laspy.read(f); c = np.asarray(l.classification)
        x, y = geo.to_local(*T.transform(np.asarray(l.x), np.asarray(l.y)))
        i = ((Y1 - np.asarray(y)) / M).astype(int); j = ((np.asarray(x) - X0) / M).astype(int)
        ok = (i >= 0) & (i < H) & (j >= 0) & (j < W)
        np.add.at(vse, (i[ok], j[ok]), 1); ok &= c == 5; np.add.at(veg, (i[ok], j[ok]), 1)
    return veg, vse


if geo.MESTO.get('les_zrnitost'):                                # koruny podle zrnitosti (+ laser): nepočítá cesty a trať v lese za les
    mask = koruny(np.asarray(big), *laser_vegetace(W, H))
else:
    mask = box(canopy, 2) > 0.3                                  # vyhladit šum (stíny, tmavé střechy)
mask |= box(L > 250, 3) > 0.5                                    # bílá = mimo Česko (ortofoto chybí): stromy nechat podle dat
Image.fromarray((mask * 255).astype(np.uint8)).save('build/les_maska.png')
json.dump({'x0y1m': [X0, Y1, M]}, open('build/les_maska.json', 'w'))
print('maska lesa', W, H, f'koruny {mask.mean() * 100:.0f} %')
