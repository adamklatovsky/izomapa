# Render čtverců se změněnou scénou ve více procesech zároveň: python nastroje/render_par.py [procesů=3]
# Bere čtverce od nejvzdálenějších, každý si zamkne souborem scene.lock, aby ho nedělaly dva procesy. Grafická karta se při renderu skoro nevytíží, brzdou je kódování dlaždic na CPU.
import hashlib, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '.')
import geo

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
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


def udelej(c):
    b = adr(c); p = f'{b}/scene.rendered'; ot = otisk(c)
    if os.path.exists(p) and open(p).read() == ot: return
    z = f'{b}/scene.lock'
    try: os.close(os.open(z, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError: return
    try:
        if os.path.exists(p) and open(p).read() == ot: return
        for s in VAR:
            args = ['node', 'render.mjs', 'mpp=0.2', f'dir={b}', f'out={b}/tiles_{s}', 'alpha=1', *G]
            args += ['season=autumn', f'mode={s}'] if s.startswith('lights') else [f'season={s}']
            for pokus in range(3):
                r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
                if r.returncode == 0 and 'dlaždice' in r.stdout and 'pageerror' not in r.stdout: break
                print('render znovu', c, s, pokus, (r.stdout + r.stderr)[-300:], flush=True); time.sleep(5)
            else:
                print('CHYBA render', c, s, flush=True); return
        open(p, 'w').write(ot)
        print(f'[{(time.time() - T0) / 60:5.1f} min] vyrenderováno', c, flush=True)
    finally:
        os.remove(z)


vse = sorted(geo.CHUNKS, key=lambda c: -(c[0] ** 2 + c[1] ** 2))
with ThreadPoolExecutor(N) as ex: list(ex.map(udelej, vse))
print('RENDER_HOTOV', flush=True)
