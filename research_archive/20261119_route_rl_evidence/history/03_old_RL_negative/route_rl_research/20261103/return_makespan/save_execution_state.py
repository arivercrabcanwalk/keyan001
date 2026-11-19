"""Persist observed engineering results and the approved objective, not success claims."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import difflib
import hashlib
import json

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
TRANSACTION = WORK / 'transaction'

def read_json(path):
    return json.loads(path.read_text())

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

state = read_json(WORK / 'STATE.json')
state['updated_at_local'] = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
state['status'] = 'G1_ENGINEERING_PACKAGE_VERIFIED_G0_NEW_MECHANISM_PENDING'
state['current_gate'] = 'G0_MECHANISM_AND_G1_FINAL_INDEPENDENT_ACCEPTANCE'
state['gates']['G0'] = 'OBJECTIVE_APPROVED; PRODUCT_FORM_NEW_ESTIMATOR_CLAIM_NO_GO; NEW_MECHANISM_PENDING'
state['gates']['G1'] = '37_CORE_PLUS_15_INDEPENDENTLY_AUTHORED_SCORER_PLUS_8_COMPATIBILITY_PASS; ISOLATED_ROLLBACK_PASS; FINAL_INDEPENDENT_DYNAMIC_ACK_PENDING'
state['research_counts']['synthetic_engineering_tests'] = {
    'root_core': 37,
    'independently_authored_scorer_root_retest': 15,
    'legacy_synthetic_compatibility': 8,
    'exact_mathematical_sample_banks': 16,
    'map_performance_samples': 0,
}
state['engineering'] = {
    'transaction': str(TRANSACTION / 'VERIFICATION.txt'),
    'receipt': str(TRANSACTION / 'RUN_RECEIPTS.json'),
    'core_tests_pass': True,
    'isolated_rollback_pass': True,
    'original_station_source_sha256': sha(TRANSACTION / 'ORIGINAL_FILE.py'),
    'original_station_source_unchanged': sha(ROOT / 'route_rl_research/20261103/joint_route_env/station_env.py') == sha(TRANSACTION / 'ORIGINAL_FILE.py'),
    'active_copy_sha256': sha(WORK / 'global_env.py'),
    'active_copy_left_modified': sha(WORK / 'global_env.py') == sha(TRANSACTION / 'MODIFIED_FILE.py'),
    'independently_authored_tests_executed_by': 'root after fix; not a new independent-agent sign-off',
    'independent_env_delivery_dynamic_final_acceptance': 'PENDING',
    'known_integer_overflow_bug': 'FIXED; original failing source and receipts preserved',
    'failure_source': str(TRANSACTION / 'PRE_FIX_SCORER.py'),
}
state['g0_candidate'] = {
    'name': 'cost_gated_product_station_trajectory_credit',
    'mathematical_finite_check': 'PASS_16_BANKS_UNDER_EXPLICIT_INDEPENDENCE',
    'independent_new_algorithm_contribution': 'NO_GO_DIRECT_SUBSTITUTION_IN_KUNTZ_CRUCINIO_JOHANSEN_EQ4',
    'compatible_with_dynamic_global_budget_policy': False,
    'trained': False,
    'decision': str(WORK / 'agents/mechanism/FINAL_DECISION.md'),
    'primary_cross_review': str(WORK / 'agents/precedents/CROSS_RESPONSE_MECHANISM.md'),
}
state['server_observation'] = {
    'time_utc': '2026-11-03T08:35:56.803960+00:00',
    'related_research_processes': 0,
    'logical_cpus': 104,
    'system_python_torch_spec_present': False,
    'nvidia_smi': None,
    'gpu_device_nodes': [],
    'accepted_reproduction_present': True,
    'old_route_stage_a_present': True,
    'new_remote_jobs_started': False,
    'other_environments_or_hosts_not_audited_for_training': True,
}
state['next_action'] = ('Complete separate final independent dynamic acceptance; freeze source-faithful new-map generator, exposed-identity exclusion, shared cost anchor and same-objective strong nonRL/cheap-control opportunity protocol. A substantively new mechanism remains necessary before G4; no training or new quality data launched.')
write_json(WORK / 'STATE.json', state)

# Historical gates and measurements remain intact. Only an authoritative pointer
# and a status wrapper are added to the prior entry point; its bytes are backed up.
old_path = ROOT / 'route_rl_research/20261103/STATE.json'
old = read_json(old_path)
old.setdefault('historical_status_before_metric_approval', old['status'])
old['status'] = 'SUPERSEDED_BY_APPROVED_RETURN_MAKESPAN_EXECUTION_STATE'
old['continuation_state'] = str(WORK / 'STATE.json')
old['continuation_plan'] = str(WORK / 'EXECUTION_PLAN.md')
old['historical_snapshot_before_pointer_update'] = str(TRANSACTION / 'ORIGINAL_route_rl_research__20261103__STATE.json')
old['continuation_semantics'] = 'Old cost-domain gates below are historical; follow continuation_state for the approved new objective.'
write_json(old_path, old)

marker = '## 2026-11-03 A方向已批准：全图返航目标工程接续'
latest = ROOT / 'LATEST_STATUS.md'
if marker not in latest.read_text():
    header = f'''{marker}
用户已回复“是的我允许 开始优化设计我们的rl吧”并要求continue。当前真实执行入口：{WORK / 'STATE.json'}；执行计划：{WORK / 'EXECUTION_PLAN.md'}；裁决：{WORK / 'ROUND_DECISION.md'}。下方“待审批/暂停”等段落为此前历史，不撤销本次用户授权；旧自动任务仍未恢复。
批准A第一包G0–G3：固定站点/站型/target-station，RL只做物理slot-target/RETURN；完整成本epsilon0（绝对容差1e-7）下min全图最终返航M。D条件改进为主、6s/12s、5%为待检验目标而非成绩；48新机会/开发+最多24隔离非RL校准/验证、16 CPU核小时科学上限。G4训练包和Formal仍另行准入。
新增scorer、FullMapRouteEnv及deadline/raw/fallback记账已实现；37核心+15独立作者scorer脚本的root修复复验+8旧接口合成检查通过，隔离回滚恢复原hash与cost reward。原station_env/V6/semfix未改，未重跑复现。工程测试不代表新地图效果；独立env/delivery最终动态签认尚待。
三方独立初判冻结后交叉：product站轨迹信用的16-bank数学核验有条件PASS，但Kuntz等product-form Eq.(4)直接覆盖其新估计器主张，G0该候选NO_GO；不改名/改K复活，不据此训练。动态全图budget策略也不满足其独立假设。
新科学地图/solver/训练/Formal均0，RL优势/创新实证/论文正文/项目完成均false。服务器08:35:56UTC相关研究进程0，未新开远端任务。下一步按新STATE完成独立终验、冻结新数据/共享锚点/同目标强非RL机会协议及真正新机制。

'''
    latest.write_text(latest.read_text().replace('# 最新研究状态\n', '# 最新研究状态\n' + header, 1))

plan_path = ROOT / 'RESEARCH_PLAN_ROUTE_RL.md'
plan_marker = '## 最新生效：用户已批准A第一阶段'
if plan_marker not in plan_path.read_text():
    prefix = f'''{plan_marker}
当前执行计划为 {WORK / 'EXECUTION_PLAN.md'}，状态为 {WORK / 'STATE.json'}。用户已批准成本不增加下最小化全图最终返航M_return，固定部署/站型/target-station，RL仅物理slot-target/RETURN；主epsilon0、绝对容差1e-7、D条件6s/12s、平均降幅目标5%且地图CI下界>0。第一包G0–G3的资源上限为48新机会/开发+最多24非RL校准/验证图、16 CPU核小时。G4训练和Formal不由工程测试自动放行。
通用新目标工程37+15+8测试和隔离回滚通过；独立最终动态签认及新机制尚待。product信用作为独立新估计器贡献已被一手原式覆盖关闭；未训练。下方保留此前成本主目标的完整历史计划，旧0.3%成本门槛不当成本轮M目标的已通过结果。

## 以下为此前成本方向计划（历史保留）
'''
    text = plan_path.read_text()
    first, rest = text.split('\n', 1)
    plan_path.write_text(first + '\n\n' + prefix + rest)

requirements = ROOT / 'USER_RESEARCH_REQUIREMENTS.md'
requirement_marker = '## 2026-11-03 最新目标审批：A方向'
if requirement_marker not in requirements.read_text():
    requirements.write_text(requirements.read_text() + f'''
{requirement_marker}
用户批准新指标规划后明确要求开始优化RL并continue。当前主问题更新为：固定站点/站型/target-station，RL仅直接构造物理路线；完整原成本不增加（共同可行anchor、epsilon0、绝对容差1e-7）下min全图最终返航M_return。D条件改进是本阶段主制度，6s/12s各检验平均5%目标及地图95%CI下界>0，不是已取得效果。
A第一包G0–G3按P2.1执行，最多48新机会/开发图+24隔离非RL校准/验证、16 CPU核小时；G4训练/新Formal及正文各依原准入，不恢复旧自动任务。当前 {WORK / 'STATE.json'} 和 {WORK / 'EXECUTION_PLAN.md'} 优先于此前原成本目标文字；原模型evaluator与历史结果不修改。
''')

diffs = []
for item in read_json(TRANSACTION / 'ORIGINAL_HASHES.json'):
    source, backup = Path(item['path']), Path(item['saved_copy'])
    assert sha(backup) == item['sha256'], str(backup)
    if source.read_bytes() != backup.read_bytes():
        diffs.append(''.join(difflib.unified_diff(backup.read_text().splitlines(True), source.read_text().splitlines(True), fromfile=str(backup), tofile=str(source))))
(TRANSACTION / 'CONTROLLED_STATE_DIFF.patch').write_text('\n'.join(diffs))
print('STATE_SAVED: approved A objective and observed tests; historical bytes preserved; RL/innovation/project completion false')
