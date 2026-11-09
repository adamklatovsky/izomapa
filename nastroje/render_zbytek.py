# Vyrenderuje čtverce, jejichž scéna se od posledního renderu změnila (otisk v scene.rendered): python nastroje/render_zbytek.py [i,j ...]
# Čtverce vypsané v argumentech se považují za už vyrenderované v aktuální podobě. Na web je pak dá nastroje/dzi_par.py.
import hashlib, os, subprocess, sys, time
sys.path.insert(0, '.')
import geo

G = ['gx0=-1646.34559672906', 'gy1=988.7958500237901']
VAR = ['autumn', 'winter', 'spring', 'summer', 'lights']
ENV = {**os.environ, 'PYTHONUTF8': '1'}
ENV.pop('IZO_MESTO', None)
T0 = time.time()


def adr(c):
    return 'build' if c == (0, 0) else f'build/c{c[0]}_{c[1]}'


def otisk(c):
    b = adr(c); h = hashlib.sha256()
    for f in ['render.html', 'render.mjs', f'{b}/scene.json', f'{b}/lightmap.png'] + [f'{b}/ground_{s}.png' for s in VAR if not s.startswith('lights')]:
        with open(f, 'rb') as fh:
            for blok in iter(lambda: fh.read(1 << 20), b''): h.update(blok)
    return h.hexdigest()


hotove = {tuple(int(v) for v in a.split(',')) for a in sys.argv[1:]}
for c in hotove: open(f'{adr(c)}/scene.rendered', 'w').write(otisk(c))
vse = sorted(geo.CHUNKS, key=lambda c: (c[0] ** 2 + c[1] ** 2, c))
for c in vse:
    b = adr(c); p = f'{b}/scene.rendered'; ot = otisk(c)
    if os.path.exists(p) and open(p).read() == ot: continue
    if os.path.exists(p): os.remove(p)
    ok = True
    for s in VAR:
        args = ['node', 'render.mjs', 'mpp=0.2', f'dir={b}', f'out={b}/tiles_{s}', 'alpha=1', *G]
        args += ['season=autumn', f'mode={s}'] if s.startswith('lights') else [f'season={s}']
        for pokus in range(3):
            r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
            if r.returncode == 0 and 'dlaždice' in r.stdout and 'pageerror' not in r.stdout: break
            print('render znovu', c, s, pokus, (r.stdout + r.stderr)[-300:], flush=True); time.sleep(5)
        else:
            ok = False; print('CHYBA render', c, s, flush=True); break
    if ok:
        open(p, 'w').write(ot)
        print(f'[{(time.time() - T0) / 60:5.1f} min] vyrenderováno', c, flush=True)
print('RENDER_HOTOV', flush=True)
