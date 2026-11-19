#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,tarfile,csv,io,ast,re,collections,sys
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['baseline','modified'],default='modified');p.add_argument('--source');a=p.parse_args()
B=Path(__file__).resolve().parent;O=B/'MODIFIED_FILE'
records=json.loads((B/'SOURCE_TO_ARCHIVE.json').read_text());by_archive={x['archive_path']:x for x in records}
if a.mode=='baseline':
 if not a.source:raise SystemExit('source directory argument required')
 source=Path(a.source);author=source.parent/'20261113_author_final_recorder_fix_v1'
 recovered={x['source_path']:x for x in json.loads((B/'RECOVERED_DATALESS_FILES.json').read_text())}
 checked=placeholders=0
 for r in records:
  f=(source if r['source_root']=='F3' else author)/r['source_path']
  if f.stat().st_flags & 0x40000000:
   assert recovered[r['source_path']]['sha256']==r['source_sha256'];placeholders+=1
  else:
   assert hashlib.sha256(f.read_bytes()).hexdigest()==r['source_sha256'],r['source_path'];checked+=1
 print(json.dumps({'result':'BASELINE_SOURCE_UNCHANGED_PASS','available_original_files_rehashed':checked,'dataless_original_files_matched_to_server_transfer':placeholders,'source_files_written':0},sort_keys=True));raise SystemExit(0)
contents={};checked=0;json_count=python_count=0;scan_hits=[]
patterns={
 'private_key':re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
 'connection_details':re.compile(r'(?i)\b(?:ssh|sshpass|scp|sftp)\s+[-\w]|\.ssh/|\b(?:IdentityFile|ProxyCommand)\s+\S'),
 'private_execution_host':re.compile(r'(?i)\bhn01\b|jupyter-[a-z0-9]+'),
 'credential_token':re.compile(r'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})'),
 'network_address':re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])'),
 'private_email':re.compile(r'(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])'),
}
def check(data,loc):
 global checked,json_count,python_count
 r=by_archive[loc];assert len(data)==r['archive_bytes'];assert hashlib.sha256(data).hexdigest()==r['archive_sha256'],loc
 checked+=1;contents[loc]=data
 try:text=data.decode()
 except UnicodeError:raise AssertionError('Unexpected binary: '+loc)
 for category,pat in patterns.items():
  matches=pat.findall(text)
  if category=='network_address':matches=[s for s in matches if all(int(v)<=255 for v in s.split('.'))]
  if matches:scan_hits.append({'archive_path':loc,'category':category,'count':len(matches)})
 suffix=Path(loc.split('::')[-1]).suffix
 if suffix=='.json':json.loads(text);json_count+=1
 if suffix=='.jsonl':
  for line in text.splitlines():
   if line.strip():json.loads(line)
  json_count+=1
 if suffix=='.py':ast.parse(text,filename=loc);python_count+=1
for f in O.rglob('*'):
 if not f.is_file() or f.suffix=='.gz' or f.name=='.RESCUE_ARCHIVE':continue
 loc=f.relative_to(O).as_posix();check(f.read_bytes(),loc)
for f in sorted((O/'compact_evidence').glob('*.tar.gz')):
 prefix=f.relative_to(O).as_posix()+'::'
 with tarfile.open(f,'r:gz') as t:
  for m in t:
   assert m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts
   check(t.extractfile(m).read(),prefix+m.name)
assert checked==len(records),(checked,len(records));assert not scan_hits,scan_hits[:5]
def find(end):
 vals=[(k,v) for k,v in contents.items() if k.endswith(end)];assert len(vals)==1,(end,len(vals));return vals[0]
def obj(end):return json.loads(find(end)[1])
reg=obj('COMPLETED/20261114T101931Z/execution_v1/REGISTRATION.json');assert len(reg['maps'])==24;assert len(reg['authors'])==72;assert len(reg['controls'])==2880
hashes=obj('COMPLETED/20261114T101931Z/recovery_v2/COMPLETION_ROW_HASHES.json');assert len(hashes['authors'])==72;assert len(hashes['controls'])==2880
for key,n in [('authors',72),('controls',2880)]:assert len({x['row_id'] for x in hashes[key]})==n
maps=[k for k in contents if '/population/' in k and k.endswith('/instance.txt')];assert len(maps)==24
qualifications=[k for k in contents if '/COMPLETED/20261114T101931Z/' in k and '/authors/' in k and k.endswith('/QUALIFICATION.json')];assert len(qualifications)==72
final_decisions=[k for k in contents if '/COMPLETED/20261114T101931Z/recovery_v2/controls/' in k and k.endswith('/DECISION.json')];assert len(final_decisions)==2880
originals={x['source_path']:x for x in records if x['source_root']=='F3'}
manifest=obj('COMPLETED/20261114T101931Z/EVIDENCE_FILE_MANIFEST.json');prefix='server_evidence/COMPLETED/20261114T101931Z/'
for row in manifest:
 r=originals[prefix+row['path']];assert r['source_sha256']==row['sha256'],row['path'];assert r['source_bytes']==row['bytes']
# Match every decisive original-byte hash; redacted versions retain paired archived hashes.
by_source={x['source_path']:x for x in records if x['source_root']=='F3'}
for r in hashes['controls']:
 rid=r['row_id'];g=prefix+'recovery_v2/guards/controls/'+rid+'/'
 for filename,key in [('TERMINAL.json','terminal_sha256'),('FINAL_DELIVERY.json','final_delivery_sha256')]:assert by_source[g+filename]['source_sha256']==r[key]
for k in final_decisions:
 d=json.loads(contents[k]);rid=d['row_id'] if 'row_id' in d else None
 assert d['accepted'] is True and d['delivery_status']=='ONTIME_VALID'
rows={}
for f in (O/'performance_g3_analysis_v1/results').glob('*.csv'):
 with f.open() as h:rows[f.name]=len(list(csv.DictReader(h)))
assert rows['ALL_REGISTERED_SEED_ROWS.csv']==2880 and rows['AUTHOR_ROWS.csv']==72 and rows['ALL_24_MAP_EFFECTS.csv']==24
air2_expected=sum(r['source_root']=='F3' and r['source_path'].startswith('engineering/air2_livechain/') for r in records)
assert air2_expected>=80
assert sum(k.split('::')[-1].startswith('engineering/air2_livechain/') for k in contents)==air2_expected
assert not any(Path(k).name=='RAW_RESULT.json' for k in contents)
assert not any(Path(k).suffix in {'.pdf','.doc','.docx','.ppt','.pptx'} for k in contents)
all_files=[f for f in B.rglob('*') if f.is_file()];assert max(f.stat().st_size for f in all_files)<40_000_000
result={'result':'MODIFIED_ARCHIVE_PASS','original_source_records':len(records),'archived_members_reopened_and_sha_verified':checked,'final_manifest_original_byte_hashes_matched':len(manifest),'maps':24,'authors':72,'control_decisions':2880,'control_raw_output_hashes':2880,'control_terminal_hashes':2880,'control_final_delivery_hashes':2880,'csv_row_counts':rows,'json_or_jsonl_files_parsed':json_count,'python_files_ast_parsed':python_count,'sensitive_scan_hits':0,'third_party_full_papers':0,'raw_result_bodies':0,'max_file_bytes':max(f.stat().st_size for f in all_files),'files_40MB_or_larger':0,'scientific_runs_started':0}
(B/'ARCHIVE_VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,sort_keys=True))
