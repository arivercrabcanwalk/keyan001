"""EXECUTION_HOST-only canonicalization of all saved exposed inputs; no new map draws."""
from pathlib import Path
from decimal import Decimal
from collections import defaultdict,Counter
import hashlib,json,os,re,socket,sys,time
assert socket.gethostname()=='EXECUTION_HOST','HN01_ONLY'
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'MODIFIED_FILE'))
import generator_v2 as gen
OUT=ROOT/'exclusions';OUT.mkdir(exist_ok=False)
INPUT=ROOT/'exposure_inputs';inventory=json.loads((INPUT/'INPUT_INVENTORY.json').read_text())
objects=defaultdict(list)
for row in inventory['sources']:objects[row['object']].append(row['source_path'])
records={};sources=[];raw_parsed={};seen_json=set();errors=[];unresolved=[];coverage={};required={};json_fixtures=[]
hex64=re.compile('[0-9a-f]{64}')
def sha(b):return hashlib.sha256(b).hexdigest()
def valid(v):return isinstance(v,str) and hex64.fullmatch(v)
def add(raw,geom,source,kind):
 if not valid(raw) or not valid(geom):return
 key=(raw,geom)
 if key not in records:records[key]={'raw_sha256':raw,'canonical_geometry_sha256':geom,'eligible_for_research':False,'sources':[],'kind':kind}
 if source not in records[key]['sources']:records[key]['sources'].append(source)
def raw_text(data,source):
 h=sha(data)
 if h not in raw_parsed:
  try:
   nodes=gen.parse_instance_text(data.decode('utf-8-sig'))
   geom=gen.canonical_geometry_identity(nodes)
   raw_parsed[h]={'canonical_geometry_sha256':geom,'targets':sum(n.kind=='target' for n in nodes),'sites':sum(n.kind=='site' for n in nodes)}
  except Exception as exc:
   errors.append({'source':source,'raw_sha256':h,'exception':type(exc).__name__+':'+str(exc)})
   return
 add(h,raw_parsed[h]['canonical_geometry_sha256'],source,'saved_raw_instance')

def fixture(d,source):
 targets=d.get('targets');stations=d.get('stations')
 if not isinstance(targets,list) or not isinstance(stations,list) or not targets or not stations:return
 try:
  nodes=[]
  for i,r in enumerate(targets,1):
   if isinstance(r,dict):row=[r['x'],r['y'],r.get('energy',r.get('service_energy')),r.get('service',r.get('service_time'))]
   elif isinstance(r,list) and len(r) in (4,5):row=r[-4:]
   else:raise ValueError('targets_not_full_node_rows')
   nodes.append(gen.Node(i,*[Decimal(str(v)) for v in row],'target'))
  for i,r in enumerate(stations,1):
   if isinstance(r,dict):xy=[r['x'],r['y']]
   elif isinstance(r,list) and len(r)==2:xy=r
   elif isinstance(r,list) and len(r)>=3:xy=r[1:3]
   else:raise ValueError('stations_not_node_rows')
   nodes.append(gen.Node(len(targets)+i,Decimal(str(xy[0])),Decimal(str(xy[1])),Decimal(0),Decimal(0),'site'))
  raw=gen.render_instance_text(nodes).encode();geom=gen.canonical_geometry_identity(nodes)
  add(sha(raw),geom,source,'json_fixture_rendered_geometry');json_fixtures.append({'source':source,'family':[len(stations),len(targets)],'geometry':geom})
 except (KeyError,ValueError,TypeError,ArithmeticError) as exc:
  # Only potential full population-domain geometry needs manual resolution.
  if (len(stations),len(targets)) in gen.PUBLISHED_FAMILIES:unresolved.append({'source':source,'reason':str(exc)})

def walk(x,source):
 if isinstance(x,list):
  for row in x:walk(row,source)
 elif isinstance(x,dict):
  geom=x.get('canonical_geometry_sha256');raw=x.get('raw_sha256',x.get('sha256',x.get('input_sha256',x.get('instance_sha256'))))
  if valid(geom):add(raw,geom,source,'saved_geometry_identity')
  text=x.get('solver_input_text') or x.get('retained_complete_or_partial_text')
  if isinstance(text,str) and text.startswith('CUST_NO'):raw_text(text.encode(),source+':embedded')
  if 'targets' in x and 'stations' in x:fixture(x,source)
  for key,val in x.items():
   if key not in ('targets','stations'):walk(val,source)

def json_source(data,source,aliases=()):
 h=sha(data)
 if h in seen_json:return
 seen_json.add(h)
 try:x=json.loads(data)
 except (ValueError,UnicodeError):return
 sources.append({'path':source,'sha256':h,'bytes':len(data),'kind':'json_evidence','aliases':list(aliases)})
 walk(x,source)
 for name in [source,*aliases]:
  base=Path(name).name
  if base in ('PERMANENT_EXCLUSION_MANIFEST.json','SYNTHETIC_SMOKE_EXCLUSION.json','SYNTHETIC_EXCLUSION_MANIFEST.json','WINDOWS_DEVELOPMENT_PROBE_EXCLUSION.json'):
   if isinstance(x,dict) and isinstance(x.get('records'),list):required.setdefault(base,(data,x))
  if name=='audit/20261104_github_execution/server_evidence/INSTANCE_PROVENANCE.json':coverage['published620']=x
  if name.endswith('20261106_method_family_B/data/REGISTRATION.json'):coverage['B44']=x['records']
  if 'sufficient_training_D' in name and base=='REGISTRATION.json' and isinstance(x,dict):coverage['D64']=x.get('records',x.get('maps',[]))
  if name.endswith('results/g3_pop/population_index.json'):coverage['old12']=x.get('maps',[]) if isinstance(x,dict) else x
  if name.endswith('results/g3_confirm/population_index.json'):coverage['old36']=x.get('maps',[]) if isinstance(x,dict) else x

for obj,aliases in objects.items():
 data=(INPUT/obj).read_bytes();assert sha(data)==Path(obj).stem
 if obj.endswith('.txt'):raw_text(data,'local:'+aliases[0])
 else:json_source(data,aliases[0],aliases[1:])
# Remote saved instances fill raw/canonical gaps, including all 620 published maps.
# Ignore interpreter/package/cache trees, never hidden credentials or live outputs.
skip={'.cache','.conda','.config','.ssh','.jupyter','.ipython','.local','.git','node_modules','site-packages','__pycache__','runtime','runtimes','env','venv','builds','classes','exposure_inputs','execution_v1'}
remote_files=0
for directory,dirs,files in os.walk('/root',followlinks=False):
 dirs[:]=[d for d in dirs if d not in skip and not d.startswith('.')]
 for name in files:
  p=Path(directory)/name
  if p.suffix.lower() not in ('.txt','.dat','.json'):continue
  try:
   if p.suffix.lower() in ('.txt','.dat'):
    with p.open('rb') as f:head=f.read(512)
    if b'CUST_NO' not in head.split(b'\n')[0]:continue
    data=p.read_bytes();raw_text(data,str(p));remote_files+=1
   elif p.stat().st_size<=100_000_000:
    data=p.read_bytes()
    if b'canonical_geometry_sha256' in data or (b'"targets"' in data and b'"stations"' in data) or name in ('INSTANCE_PROVENANCE.json','REGISTRATION.json'):
     json_source(data,str(p));remote_files+=1
  except (OSError,UnicodeError) as exc:errors.append({'source':str(p),'io_exception':str(exc)})
# Required manifests remain byte-identical and retain the generator's real gate.
for name,(data,x) in required.items():(OUT/name).write_bytes(data)
assert len(required)==4,sorted(required)
base=gen.ExclusionIndex.from_paths([OUT/n for n in sorted(required)])
base.require_research_ready()
# Source aliases can be byte-identical snapshots; read authoritative local IDs
# even when the object's content was already encountered elsewhere.
for key,name in [('published620','audit/20261104_github_execution/server_evidence/INSTANCE_PROVENANCE.json'),('B44','joint_weather_emergency/20261106_method_family_B/data/REGISTRATION.json')]:
 row=next(r for r in inventory['sources'] if r['source_path']==name);x=json.loads((INPUT/row['object']).read_bytes());coverage[key]=x if isinstance(x,list) else x['records']
checks={}
for label,count in [('published620',620),('B44',44)]:
 rows=coverage[label];assert len(rows)==count,(label,len(rows))
 missing=[]
 for r in rows:
  raw=r.get('raw_sha256',r.get('sha256',r.get('input_sha256')))
  if raw not in raw_parsed:missing.append({'raw':raw,'path':r.get('path')})
 checks[label]={'registered_rows':len(rows),'raw_nodes_independently_canonicalized':len(rows)-len(missing),'missing':missing}
 assert not missing,(label,missing[:3])
# D64 is authoritative on EXECUTION_HOST; resolve its registration explicitly.
dregs=list(Path('/root/joint_weather_emergency').glob('*sufficient*D*/data/REGISTRATION.json'))
if not dregs:dregs=list(Path('/root/joint_weather_emergency').glob('*training*/data/REGISTRATION.json'))
assert dregs,'D64_REGISTRATION_REQUIRED'
for file in dregs:
 x=json.loads(file.read_text());rows=x.get('records',x.get('maps',[]))
 if len(rows)!=64:continue
 missing=[r for r in rows if r.get('raw_sha256',r.get('sha256',r.get('input_sha256'))) not in raw_parsed]
 checks['D64']={'source':str(file),'source_sha256':sha(file.read_bytes()),'registered_rows':64,'raw_nodes_independently_canonicalized':64-len(missing),'missing':missing}
 assert not missing,('D64',missing[:2])
assert 'D64' in checks,'D64_64_ROW_SOURCE_REQUIRED'
# Unresolved JSON fields that are only route-ID arrays are not node sources;
# original raw maps above remain mandatory. Save diagnostics rather than hiding.
byraw={r['raw_sha256'] for r in records.values()}
result={'schema':'latest_exposed_union_v1','status':'COMPLETE_SAVED_INPUT_UNION','created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'records':list(records.values()),'sources':sources,'record_count':len(records),'raw_unique':len(byraw),'canonical_unique':len({r['canonical_geometry_sha256'] for r in records.values()}),'raw_instances_independently_parsed':len(raw_parsed),'remote_evidence_files':remote_files,'required_population_checks':checks,'json_geometry_fixtures':json_fixtures,'unresolved_json_non_node_or_ambiguous_fields':unresolved,'parse_or_io_diagnostics':errors,'new_scientific_maps':0}
(OUT/'LATEST_EXPOSED_UNION.json').write_text(json.dumps(result,indent=2)+'\n')
full=gen.ExclusionIndex([*base.records,*records.values()],base.sources);full.require_research_ready()
summary={k:v for k,v in result.items() if k not in ('records','sources','json_geometry_fixtures','parse_or_io_diagnostics','unresolved_json_non_node_or_ambiguous_fields')}
summary.update(json_geometry_fixture_count=len(json_fixtures),unresolved_json_field_count=len(unresolved),parse_io_diagnostic_count=len(errors),union_sha256=sha((OUT/'LATEST_EXPOSED_UNION.json').read_bytes()))
(OUT/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,sort_keys=True))
