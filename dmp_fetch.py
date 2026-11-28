# stáhne listy DMP 1G (ČÚZK, CC BY 4.0, laserové skenování povrchu) pokrývající budovy mapy do build/dmp/
# python dmp_fetch.py   (seznam listů z ATOM feedu ČÚZK se stáhne do build/dmp/atom.xml, ~24 MB)
import sys, re, glob, os, shutil, subprocess
import pyarrow.parquet as pq, shapely
os.makedirs('build/dmp', exist_ok=True)
A = 'build/dmp/atom.xml'
# stahuje se přes .part: useknutý seznam by se příště bral jako hotový a část budov by tiše zůstala bez laserových výšek
if not os.path.exists(A):
    subprocess.run(['curl', '-sfL', '-m', '300', '-o', A + '.part', 'https://atom.cuzk.gov.cz/DMP1G-SJTSK/DMP1G-SJTSK.xml'], check=True)
    os.replace(A + '.part', A)
s = open(A, encoding='utf8').read()
if '</feed>' not in s[-100:]: os.remove(A); sys.exit(f'{A} byl useknutý (smazán), spusť dmp_fetch.py znovu')
sheets = []
for e in s.split('<entry>')[1:]:
    p = re.search(r'<georss:polygon>(.*?)<', e); k = re.search(r'DMP1G-SJTSK_([A-Z0-9]+)\.xml', e)
    if p and k:
        v = list(map(float, p.group(1).split())); sheets.append((k.group(1), min(v[1::2]), min(v[0::2]), max(v[1::2]), max(v[0::2])))
b = {}
for f in glob.glob('data*/building.parquet'):
    t = pq.read_table(f, columns=['id', 'bbox']).to_pylist()
    for r in t: b[r['id']] = r['bbox']
xs = shapely.box([r['xmin'] for r in b.values()], [r['ymin'] for r in b.values()], [r['xmax'] for r in b.values()], [r['ymax'] for r in b.values()])
tree = shapely.STRtree(xs); use = [n for n, *q in sheets if len(tree.query(shapely.box(*q)))]
print(len(b), 'budov', len(use), 'listů')
for n in use:
    z = f'build/dmp/{n}.laz'
    if os.path.exists(z): continue
    zp = f'build/dmp/{n}.zip'
    subprocess.run(['curl', '-sfL', '-m', '180', '-o', zp + '.part', f'https://openzu.cuzk.cz/opendata/DMP1G/epsg-5514/{n}.zip'], check=True)
    os.replace(zp + '.part', zp)
    # rozbalit vedle a .laz přesunout až celý: přerušené rozbalení by jinak nechalo useknutý list, který se příště přeskočí
    shutil.rmtree('build/dmp/rozbaleno', ignore_errors=True)   # zbytek dřívějšího přerušeného rozbalení
    subprocess.run(['unzip', '-oq', zp, '-d', 'build/dmp/rozbaleno'], check=True)
    for f in glob.glob('build/dmp/rozbaleno/*'): os.replace(f, 'build/dmp/' + os.path.basename(f))
    os.remove(zp)
print('hotovo', len(glob.glob('build/dmp/*.laz')))
