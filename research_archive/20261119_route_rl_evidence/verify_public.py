"""Read-only verification; no solver/model/runtime required."""
import hashlib, tarfile, csv
from pathlib import Path
root=Path(__file__).resolve().parent
def sha(f):
 h=hashlib.sha256()
 while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
manifest=(root/'SHA256SUMS').read_text().splitlines()
for ln in manifest:
 h,name=ln.split('  ',1); assert root in (root/name).resolve().parents
 with (root/name).open('rb') as f: assert sha(f)==h,name
for arc,table,n in [('F3_RAW_RESULTS','RAW',2880),('NO_WIND_ORIGINAL_RESULTS','NO_WIND',465),('SEMFIX_SERVER_MATRIX','SEMFIX_SERVER',11407)]:
 folder=root/'server_originals'
 with (folder/(table+'_SHA256.tsv')).open() as f:
  expected={r['member']:r['sha256'] for r in csv.DictReader(f,delimiter='\t')}
 assert len(expected)==n
 seen=set()
 with tarfile.open(folder/(arc+'.tar.gz'),mode='r|gz') as t:
  for m in t:
   assert m.isfile() and m.name in expected and m.name not in seen,m.name
   assert sha(t.extractfile(m))==expected[m.name],m.name
   seen.add(m.name)
 assert seen==expected.keys()
 print(arc,len(seen),'OK')
print('FILES',len(manifest),'OK')
