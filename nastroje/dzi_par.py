# Dlaždice webu souběžně pro čtverce, které na webu ještě nejsou v aktuální podobě (otisk v scene.sha): python nastroje/dzi_par.py [workers=8]
import os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '.'); sys.path.insert(0, 'nastroje')
import geo

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8
PY = sys.executable
ENV = {**os.environ, 'PYTHONUTF8': '1'}
ENV.pop('IZO_MESTO', None)
T0 = time.time()
VAR = ['autumn', 'winter', 'spring', 'summer', 'lights']


def adr(c):
    return 'build' if c == (0, 0) else f'build/c{c[0]}_{c[1]}'


def otisk(c):
    import hashlib
    b = adr(c); h = hashlib.sha256()
    for f in ['render.html', 'render.mjs', f'{b}/scene.json', f'{b}/lightmap.png'] + [f'{b}/ground_{s}.png' for s in VAR if not s.startswith('lights')]:
        with open(f, 'rb') as fh:
            for blok in iter(lambda: fh.read(1 << 20), b''): h.update(blok)
    return h.hexdigest()


def udelej(c):
    b = adr(c); ot = otisk(c); p = f'{b}/scene.sha'
    if os.path.exists(p) and open(p).read() == ot: return c, 'beze změny'
    q = f'{b}/scene.rendered'
    if not os.path.exists(q) or open(q).read() != ot: return c, 'NEVYRENDEROVÁNO'
    args = [PY, 'dzi.py'] + ([] if c == (0, 0) else ['--chunk', f'{c[0]},{c[1]}'])
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
    if r.returncode: return c, 'CHYBA ' + r.stderr[-300:]
    open(p, 'w').write(ot)
    return c, 'na webu'


vse = sorted(geo.CHUNKS, key=lambda c: (c[0] ** 2 + c[1] ** 2, c))
zbyva = 0
with ThreadPoolExecutor(N) as ex:
    for c, st in ex.map(udelej, vse):
        print(f'[{(time.time() - T0) / 60:5.1f} min]', c, st, flush=True)
        if st != 'na webu' and st != 'beze změny': zbyva += 1
if zbyva:                                # klikací vrstva a stránka až po posledním čtverci, jinak se počítají zbytečně při každém průchodu
    print('čeká čtverců', zbyva, flush=True); sys.exit()
for a in (['preview.py'], ['overlay.py'], ['mhd.py'], ['set_status.py', 'hotovo'], ['build_html.py']):
    r = subprocess.run([PY, *a], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
    print(a[0], 'exit', r.returncode, (r.stdout.strip().splitlines() or [''])[-1][:110], r.stderr[-200:] if r.returncode else '', flush=True)
print('WEB_HOTOV', flush=True)
