from pathlib import Path
import hashlib,json,os,platform,socket,sys,time
AUTHOR=Path('/root/rivermind-data/lunwen_engineering/20261113_author_final_recorder_fix_v1')
JDK=Path('/root/lunwen_engineering/20261112_takeover_completion/runtime/jdk17')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def freeze(root):
 assert socket.gethostname()=='EXECUTION_HOST'
 root=Path(root);source=root/'MODIFIED_FILE';files=[]
 for p in source.rglob('*'):
  if p.is_file():files.append(p)
 for relative in ['validation','frozen/baselines','frozen/env','frozen/wind_adapted_fixed','builds/wind_adapted_fixed']:
  files.extend(p for p in (AUTHOR/relative).rglob('*') if p.is_file() and p.suffix in ('.py','.java','.class','.json'))
 files += [AUTHOR/'SOURCE_LOCK.json',AUTHOR/'INPUTS.json',JDK/'bin/java',JDK/'bin/javac',JDK/'lib/server/libjvm.so',Path(sys.executable).resolve(),root/'AUTHORIZATION.json',root/'EXPERIMENT_FREEZE.json',root/'exclusions/LATEST_EXPOSED_UNION.json']
 for p in sorted((root/'exclusions').glob('*EXCLUSION*.json')):files.append(p)
 files.append(root/'PRIOR_EVIDENCE_MANIFEST.json')
 prior=json.loads((root/'PRIOR_EVIDENCE_MANIFEST.json').read_text())
 for row in prior['files']:
  assert sha(row['path'])==row['sha256'],row['path']
  files.append(Path(row['path']))
 rows=[{'path':str(p.resolve()),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(files))]
 manifest={'schema':'f3_g3_full_source_closure_v1','host':socket.gethostname(),'python':sys.version,'platform':platform.platform(),'source_files':rows,'author_root':str(AUTHOR),'java_source_profile':'wind_adapted_fixed','author_manifest_sha256':sha(AUTHOR/'builds/wind_adapted_fixed/BUILD_MANIFEST.json'),'environment':{k:os.environ.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','PYTHONDONTWRITEBYTECODE']},'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 path=root/'SOURCE_CLOSURE.json'
 with path.open('x') as f:json.dump(manifest,f,indent=2,sort_keys=True);f.write('\n')
 return manifest

def verify(root):
 root=Path(root);data=json.loads((root/'SOURCE_CLOSURE.json').read_text())
 for row in data['source_files']:assert sha(row['path'])==row['sha256'],row['path']
 return data

def loaded_modules(out):
 rows=[]
 for name,module in sorted(sys.modules.items()):
  file=getattr(module,'__file__',None)
  if file and Path(file).is_file():rows.append({'module':name,'path':str(Path(file).resolve()),'sha256':sha(file)})
 Path(out).write_text(json.dumps(rows,indent=2)+'\n')
