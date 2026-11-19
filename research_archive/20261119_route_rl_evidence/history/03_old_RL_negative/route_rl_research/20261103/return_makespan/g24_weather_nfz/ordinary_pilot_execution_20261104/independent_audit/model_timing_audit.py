"""Independent saved checkpoint, physical trace and parent-wall evidence audit."""
from pathlib import Path
import hashlib
import json
import math

SEEDS=(103,211,307)
REGIMES=('frozen_bc','ppo','continued_bc')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def near(a,b):return type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and math.isfinite(b) and abs(a-b)<=1e-7
def digest(state):
    import torch
    h=hashlib.sha256()
    def visit(v):
        if torch.is_tensor(v):
            x=v.detach().cpu().contiguous();h.update(str((str(x.dtype),tuple(x.shape))).encode());h.update(x.numpy().tobytes())
        elif isinstance(v,dict):
            for k in sorted(v,key=lambda x:str(x)):h.update(repr(k).encode());visit(v[k])
        elif isinstance(v,(list,tuple)):
            for x in v:visit(x)
        else:h.update(repr(v).encode())
    visit(state);return h.hexdigest()

def audit_models_and_timing(reg,out,check,replay_saved):
    out=Path(out);models=read(out/'MODELS.json');records=models['records'];regsha=sha(reg['_registration_path'])
    check(models.get('registration_sha256')==regsha,'model registration identity')
    keys=[(r['seed'],r['regime']) for r in records]
    check(len(keys)==9 and len(set(keys))==9 and set(keys)=={(s,r) for s in SEEDS for r in REGIMES},'all nine model slots exactly once')
    trainpath=out/'TRAIN_MANIFEST.json';train=read(trainpath) if trainpath.exists() else {}
    eligible={r['id'] for r in train.get('cases',[])};manifestsha=sha(trainpath) if trainpath.exists() else None
    commonrows=models.get('common_records',[]);common_by={r['seed']:r for r in commonrows}
    check(len(common_by)==len(commonrows) and set(common_by).issubset(SEEDS),'common seed identities')
    expectedtrain={f'TRAIN_{i}' for i in range(1,7)};check(eligible.issubset(expectedtrain),'optimizer TRAIN identity domain')
    summaries=[];checkpoints={};stage_reports=[]

    def parent_receipt(p,label,cap):
        if not p:return
        started=p.get('started_abs');ended=p.get('ended_abs');deadline=p.get('deadline_abs')
        if ended is not None:check(near(p.get('stage_wall_s'),ended-started),label+' external wall accounting')
        if started is not None and deadline is not None:check(deadline-started<=cap+1e-6,label+' external hard cap')
        if p.get('status')=='completed':
            check(p.get('exit_code')==0 and not p.get('hard_killed') and ended is not None and ended<=deadline and p.get('stage_wall_s',1e9)<=cap,label+' completed parent timing')

    def saved_episodes(raw,label,field):
        episodes=raw.get(field,[]);counts={'returned_episodes':len(episodes),'complete':0,'partial':0,'transitions':0}
        for i,ep in enumerate(episodes):
            elabel=f'{label}/{field}/{i}';name=ep.get('map');check(name in eligible,elabel+' eligible TRAIN only')
            events=ep.get('events');n=ep.get('transition_count')
            check(isinstance(events,list) and type(n)==int and n==len(events),elabel+' physical prefix/count')
            check('transitions' not in ep,elabel+' optimizer tensors not serialized')
            counts['transitions']+=n if type(n)==int else 0
            if not isinstance(events,list):continue
            for j,event in enumerate(events):
                check(event.get('step')==j+1 and type(event.get('station_idx'))==int and type(event.get('slot'))==int and event['slot'] in (0,1),elabel+' physical action identity')
                check(event.get('physical_action')==('RETURN' if event.get('target_id') is None else 'TARGET'),elabel+' TARGET/RETURN correspondence')
                check(type(event.get('reward')) in (int,float) and math.isfinite(event['reward']),elabel+' finite training reward')
            if ep.get('complete'):
                counts['complete']+=1;result=ep.get('result')
                check(ep.get('failure') is None and isinstance(result,dict) and isinstance(result.get('solution'),dict),elabel+' complete saved solution')
                if isinstance(result,dict) and isinstance(result.get('solution'),dict):
                    sol=result['solution'];routes=[[[],[]] for _ in sol['routes']];pending={};ok=True
                    for event in events:
                        si,slot=event['station_idx'],event['slot'];target=event.get('target_id');key=(si,slot)
                        if not 0<=si<len(routes):ok=False;break
                        pending.setdefault(key,[])
                        if target is None:
                            if not pending[key]:ok=False;break
                            routes[si][slot].append(pending[key]);pending[key]=[]
                        else:pending[key].append(target)
                    check(ok and not any(pending.values()) and routes==sol['routes'],elabel+' complete physical prefix reconstructs stored route')
                    replay_saved(name,sol,result.get('replay'),elabel)
            else:
                counts['partial']+=1;check(ep.get('result') is None and bool(ep.get('failure')),elabel+' failed partial explicitly retained')
        return counts

    for seed in SEEDS:
        for regime in REGIMES:
            row=next((r for r in records if r.get('seed')==seed and r.get('regime')==regime),{})
            label=f'{regime}/{seed}';status=row.get('status');check(status in ('completed','failed','skipped'),label+' explicit status')
            parent=common_by.get(seed,{}) if regime=='frozen_bc' else row.get('receipt',{})
            parent_receipt(parent,label,300 if regime=='frozen_bc' else 600)
            raw=parent.get('raw') or {};stage='common' if regime=='frozen_bc' else 'continued-bc' if regime=='continued_bc' else 'ppo'
            stagedir=out/'training'/f'{stage}_{seed}';progresspath=stagedir/'PROGRESS.json'
            progress=read(progresspath) if progresspath.exists() else None
            if parent and parent.get('started_abs')!=parent.get('deadline_abs') and parent.get('error')!='deadline_before_launch':
                # Import failure may precede trainer main; retain that as a failed stage.
                if raw:check(progress is not None,label+' durable trainer progress missing')
            diagnostics=progress if progress and (not raw or len(progress.get('episodes',progress.get('greedy_gate',[])))>len(raw.get('episodes',raw.get('greedy_gate',[])))) else raw
            if diagnostics:
                check(diagnostics.get('seed')==seed and diagnostics.get('regime')==stage,label+' trainer seed/stage')
                check(diagnostics.get('trainer_sha256')==reg['dependencies'].get(reg['trainer']),label+' frozen trainer source')
            saved=saved_episodes(diagnostics,label,'greedy_gate' if regime=='frozen_bc' else 'episodes') if diagnostics else {}
            if regime=='ppo' and diagnostics:check(saved.get('transitions',0)==diagnostics.get('unique_environment_transitions'),label+' unique transitions distinct from presentations')
            if status=='completed':
                check(parent.get('status')=='completed' and raw.get('status')=='completed' and raw.get('deadline_met') is True,label+' completed stage receipt')
                check(raw.get('checkpoint')==row.get('checkpoint') and raw.get('checkpoint_sha256')==row.get('checkpoint_sha256'),label+' parent checkpoint binding')
                if regime=='frozen_bc':
                    check(raw.get('completed_epochs')==400 and raw.get('gate_pass') is True,label+' exact400 and BCgate')
                    check([ep.get('map') for ep in raw.get('greedy_gate',[])]==sorted(eligible) and all(ep.get('complete') for ep in raw.get('greedy_gate',[])),label+' one greedy gate per eligible TRAIN')
                    demos=raw.get('demonstration_transitions',0)
                    check(type(demos)==int and 0<demos<=4096 and raw.get('action_presentations')==400*demos and raw.get('gradient_steps')==400*((demos+63)//64),label+' BC epoch/presentation/gradient accounting')
                if regime=='ppo':check(raw.get('last_completed_update',0)>0 and raw.get('gradient_steps',0)>0,label+' actual positive completed PPO updates')
                if regime=='continued_bc':check(row.get('wall_matched') is True and raw.get('target_reached') is True and raw.get('gradient_steps',0)>0,label+' completed continuation is wall matched with gradients')
                try:
                    import torch
                    path=Path(row['checkpoint']);check(sha(path)==row['checkpoint_sha256'],label+' checkpoint byte hash')
                    checkpoint=torch.load(path,map_location='cpu',weights_only=True)
                    check(checkpoint.get('schema')=='ordinary_route_pilot_checkpoint_p2' and checkpoint.get('observation_schema')=='weather_context_bound_candidates44_engineering_v1' and checkpoint.get('candidate_dim')==44 and checkpoint.get('hidden_dim')==64,label+' model architecture schema')
                    check(checkpoint.get('seed')==seed and checkpoint.get('manifest_sha256')==manifestsha and checkpoint.get('regime')==('common_bc' if regime=='frozen_bc' else stage),label+' checkpoint TRAIN/seed/regime')
                    th,oh=digest(checkpoint['model_state']),digest(checkpoint['optimizer_state']);checkpoints[(seed,regime)]=(th,oh)
                    check(th==raw.get('tensor_sha256') and oh==raw.get('optimizer_sha256'),label+' saved tensor+Adam hash')
                    check(checkpoint.get('last_completed_update')==raw.get('last_completed_update'),label+' checkpoint completed-update counter')
                except Exception as exc:check(False,label+' checkpoint audit exception '+repr(exc))
            else:check(row.get('checkpoint') is None,label+' failed/skipped not promoted through checkpoint')
            stage_reports.append({'seed':seed,'regime':regime,'status':status,'parent_wall_s':parent.get('stage_wall_s'),'saved_progress_exists':progress is not None,'diagnostic_episode_counts':saved,'in_flight_unreturned_episode':'UNKNOWN_IF_KILLED','gradient_steps':diagnostics.get('gradient_steps'),'action_presentations':diagnostics.get('action_presentations'),'unique_environment_transitions':diagnostics.get('unique_environment_transitions'),'last_completed_update':diagnostics.get('last_completed_update')})

    common_ok=all(next(r for r in records if r['seed']==s and r['regime']=='frozen_bc')['status']=='completed' for s in SEEDS)
    for seed in SEEDS:
        common=checkpoints.get((seed,'frozen_bc'))
        for regime in ('ppo','continued_bc'):
            row=next(r for r in records if r['seed']==seed and r['regime']==regime);raw=(row.get('receipt') or {}).get('raw') or {}
            if not common_ok:check(not row.get('receipt') and row['status']=='skipped',f'{regime}/{seed} continuation skipped after any BCfailure')
            if raw and raw.get('initial_tensor_sha256'):
                check(common is not None and (raw.get('initial_tensor_sha256'),raw.get('initial_optimizer_sha256'))==common,f'{regime}/{seed} exact common tensor and Adam clone')
            if regime=='ppo' and row['status']=='completed':check(checkpoints.get((seed,'ppo'),(None,))[0]!=common[0],f'ppo/{seed} saved optimized tensors changed')
        ppo=next(r for r in records if r['seed']==seed and r['regime']=='ppo');cbc=next(r for r in records if r['seed']==seed and r['regime']=='continued_bc')
        if cbc.get('receipt'):
            pp=ppo.get('receipt') or {};cp=cbc['receipt'];raw=cp.get('raw') or {};target=pp.get('stage_wall_s')
            check(ppo['status']=='completed',f'continued_bc/{seed} paired PPO target exists')
            if raw.get('continued_loop_finished_abs') is not None:
                final=cp['ended_abs']-raw['continued_loop_finished_abs'];mismatch=cp['stage_wall_s']-target;tol=raw.get('last_batch_duration_s',0)+final
                matched=cp['status']=='completed' and raw.get('status')=='completed' and raw.get('target_reached') is True and raw.get('gradient_steps',0)>0 and final>=0 and mismatch>=-1e-9 and mismatch<=tol+1e-6
                check(near(raw.get('target_wall_s'),target),f'continued_bc/{seed} child actual PPO wall target')
                check(cbc.get('wall_matched') is matched,f'continued_bc/{seed} independent actual-wall match verdict')
                if cbc['status']=='completed':
                    for k,v in [('target_wall_s',target),('signed_wall_mismatch_s',mismatch),('matching_tolerance_s',tol),('parent_finalization_cleanup_parse_s',final)]:check(near(cbc.get(k),v),f'continued_bc/{seed} '+k)
                summaries.append({'seed':seed,'paired_PPO_parent_wall_s':target,'CBC_parent_wall_s':cp['stage_wall_s'],'loading_wall_s':raw.get('loading_wall_s'),'actual_parent_finalization_cleanup_parse_s':final,'last_batch_duration_s':raw.get('last_batch_duration_s'),'mismatch_s':mismatch,'tolerance_s':tol,'matched':matched})
    comparisons=read(out/'validation/COMPARISONS.json');lock=out/'validation/VALIDATION_ONCE.lock'
    ppo_ok=any(r['regime']=='ppo' and r['status']=='completed' for r in records)
    if not common_ok or not ppo_ok:check(not lock.exists() and all(not r.get('process') and r.get('selected') is None for r in comparisons),'failed BC/allPPO barrier prevents actual validation')
    if lock.exists():
        obj=read(lock);check(obj.get('registration_sha256')==regsha and obj.get('models_sha256')==sha(out/'MODELS.json'),'exclusive validation lock model+source freeze')
        check(common_ok and ppo_ok,'validation prerequisites')
    elif any(r.get('process') for r in comparisons):check(False,'actual validation without consumed lock')
    return {'stage_reports':stage_reports,'wall_matching':summaries,'all_three_BC_gates_passed':common_ok,'any_PPO_completed':ppo_ok,'planned_common_seeds':3,'planned_model_slots':9,'saved_tensor_change_is_not_useful_RL_evidence':True}
