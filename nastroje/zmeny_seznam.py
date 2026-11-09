# Seznam souborů pro nahrání jen změněných čtverců: python nastroje/zmeny_seznam.py -> build/nahraj_seznam.txt (cesty relativně k site/)
# Porovná otisky scene.sha s build/nahrano.json (stav při posledním nahrání). Stránka, popisky a MHD jdou vždy. --zapis uloží aktuální stav jako nahraný.
import json, os, sys
sys.path.insert(0, '.')
import geo
STAV = 'build/nahrano.json'


def adr(c):
    return 'build' if c == (0, 0) else f'build/c{c[0]}_{c[1]}'


ted = {f'{i},{j}': open(f'{adr((i, j))}/scene.sha').read() for i, j in geo.CHUNKS if os.path.exists(f'{adr((i, j))}/scene.sha')}
if '--zapis' in sys.argv:
    json.dump(ted, open(STAV, 'w')); print('stav uložen', len(ted)); sys.exit()
stary = json.load(open(STAV)) if os.path.exists(STAV) else {}
zmena = [k for k, v in ted.items() if stary.get(k) != v]
vrstvy = ['autumn', 'winter', 'spring', 'summer', 'lights']
sez = [f'./{n}' for n in sorted(os.listdir('site')) if n not in ('tiles', 'galerie')]
for k in zmena:
    i, j = k.split(',')
    if k == '0,0': sez += [f'./tiles/{v}' for v in vrstvy]
    else: sez.append(f'./tiles/c{i}_{j}')
open('build/nahraj_seznam.txt', 'w', encoding='utf-8', newline='\n').write('\n'.join(sez) + '\n')
print('změněných čtverců', len(zmena), sorted(zmena))
