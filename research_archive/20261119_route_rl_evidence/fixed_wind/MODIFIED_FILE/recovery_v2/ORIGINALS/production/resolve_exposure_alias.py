from pathlib import Path
import hashlib,json,socket,shutil
assert socket.gethostname()=='EXECUTION_HOST'
root=Path(__file__).resolve().parent.parent;p=root/'exclusions/LATEST_EXPOSED_UNION.json'
x=json.loads(p.read_text());resolved=[]
for row in x['unresolved_json_non_node_or_ambiguous_fields']:
 source=Path(row['source']);raw=source.read_bytes();d=json.loads(raw);ref=d.get('instance_sha256')
 matches=[r for r in x['records'] if r['raw_sha256']==ref]
 assert matches,('UNRESOLVED_EXPOSURE',row)
 resolved.append({'source':str(source),'source_sha256':hashlib.sha256(raw).hexdigest(),'resolution':'EXACT_ORIGINAL_RAW_INSTANCE_ALREADY_CANONICALIZED_AND_EXCLUDED','referenced_instance_sha256':ref,'canonical_geometry_sha256':matches[0]['canonical_geometry_sha256']})
shutil.copy2(p,root/'exclusions/ORIGINAL_BEFORE_ALIAS_RESOLUTION.json')
x['resolved_json_geometry_references']=resolved;x['unresolved_json_non_node_or_ambiguous_fields']=[]
p.write_text(json.dumps(x,indent=2)+'\n')
s=json.loads((p.parent/'SUMMARY.json').read_text());s['unresolved_json_field_count']=0;s['resolved_original_references']=resolved;s['union_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();(p.parent/'SUMMARY.json').write_text(json.dumps(s,indent=2)+'\n')
print(json.dumps({'status':'ALL_AMBIGUOUS_GEOMETRY_REFERENCES_RESOLVED','count':len(resolved),'union_sha256':s['union_sha256']}))
