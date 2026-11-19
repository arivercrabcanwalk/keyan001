"""Finalize document/status records from completed EXECUTION_HOST receipts; no science runs."""
from pathlib import Path
import datetime
import difflib
import hashlib
import json
import os
import shlex

A = Path(__file__).resolve().parent
P = A.parent
ROOT = P.parent.parent
REMOTE = '/root/rivermind-data/liu_f3_g3_authorized_20261114_v1/performance_g3_analysis_v1'
LABEL = 'F3_G3_QUALIFICATION_OPPORTUNITY_PASS_LIMITED_DOMAIN_WITH_INFERENCE_PREREG_DEVIATION'
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n')

protected = {
    'route_rl_research/20261103/STATE.json': 'a7eae55ee6af425a3f35644176ecd35d447b097c8aac3ad02670b5b732e0376b',
    'route_rl_research/20261103/return_makespan/STATE.json': 'b0b5aab03caa333d5ea7e75c85261847ecee045d19a1d0bbe3d06b5b064932a9',
    'joint_weather_emergency/20261112_takeover_completion/STATE.json': 'b531bb400eead532bae296e9664da74fbf1bdea03c385c913668146946b1c4c1',
}
intent = read(A/'ANALYSIS_INTENT.json')
summary = read(A/'results/SUMMARY.json')
audit = read(A/'results/INDEPENDENT_AUDIT.json')
ledger = read(A/'FINAL_LEDGER_RECHECK.json')['result']
for rel, expected in protected.items():
    assert sha(ROOT/rel) == expected, rel
for name, target in [('STATE.json', P/'STATE.json'), ('REPORT_ZH.md', P/'REPORT_ZH.md'), ('LATEST_STATUS.md', ROOT/'LATEST_STATUS.md')]:
    assert sha(A/'ORIGINALS'/name) == intent['original_snapshot_hashes'][name]
    assert sha(target) == intent['original_snapshot_hashes'][name], 'Document drift: '+name
for row in read(A/'LOCAL_SOURCE_MANIFEST.json'):
    assert sha(A/'MODIFIED_FILE'/row['path']) == row['sha256']
assert sha(A/'results/SUMMARY.json') == '611a6214fb60393fc808cd8e76c5d7b5676b832f1cfa6a9126edd5c7b0b4ee2d'
assert audit['status'] == 'INDEPENDENT_ORIGINAL_RECORD_FSUM_AUDIT_PASS'
assert audit['summary_sha256'] == sha(A/'results/SUMMARY.json')
assert sha(A/'ROLLBACK_COPY/STATE.json') == sha(A/'ORIGINALS/STATE.json')
assert not (A/'ROLLBACK_COPY/MODIFIED_FILE/aggregate.py').exists()
assert os.access(A/'ROLLBACK.sh', os.X_OK)

adjudication = {
    'status': LABEL,
    'adjudicated_at_utc': NOW,
    'decision_owner': 'root',
    'numerical_execution_host': 'EXECUTION_HOST',
    'scope': 'Registered F3 author/strong-nonRL qualification and descriptive opportunity only',
    'project_wide_unconditional_G3_pass': False,
    'confirmatory_inference_preregistration_satisfied': False,
    'population': {'base_maps': 24, 'fixed_families': 12, 'maps_per_family': 2, 'winds_m_per_min': [[0,0],[240,0],[0,480]], 'run_seeds_per_method_deadline_cell': 10, 'author_anchors': 72, 'control_rows': 2880, 'independent_unit': 'base map; n=24'},
    'decision_checks': {
        'registered_population_complete': True,
        'same_wind_full_authors_qualified': 72,
        'strong_controls_ontime_valid': 2880,
        'missing_duplicate_failure_skipped_rows': 0,
        'all_rows_ITT_equals_valid_only': True,
        'per_row_cost_cap_audited': True,
        'complete_process_exit_and_cleanup_audited': True,
        'all_seed_wind_family_deadline_summaries_present': True,
        'independent_original_record_mean_audit': audit['status'],
        'global_deployment_rule_frozen_after_calibration': True,
        'new_G3_effect_cutoff_added': False,
        'RL_success_required_for_this_G3_stage': False,
    },
    'method_budget_summary': summary['method_budget_summary'],
    'eight_contrasts': summary['eight_contrasts'],
    'deployment': summary['deployment_selection'],
    'retained_deviations': [
        'Bootstrap settings and comparison-family details were first specified postcollection; current intervals are exploratory, not preregistered confirmation.',
        'Bonferroni percentile intervals do not repair missing preregistration; only two maps per fixed family makes coverage fragile.',
        'Global method selection is calibration on these exposed maps; subsequent DEV/Formal must use fresh identities.',
    ],
    'claim_limits': summary['claim_limits'] + [
        'Author generation lies outside the 6/12s control budget: reported gains are conditional refinement, not end-to-end equal-wall superiority over the author.',
        'No equivalence claim follows from a 12s H-minus-ALNS interval containing zero.',
        'No wind-speed/direction main effects, arbitrary-wind generalization, or within-family superiority claims.',
        'Broader project comparator families, same-component BC/standard-RL/ablation obligations and split admission remain separately pending.',
    ],
    'G0': 'NOT_PASSED; no demonstrated RL learning increment',
    'training_updates': 0,
    'checkpoints': 0,
    'Formal': 0,
    'new_solves_in_analysis': 0,
    'reviewers': [
        {'agent':'g3_gate_adjudication_20261114','model':'gpt-6.1-sol','reasoning_effort':'xhigh','fork_turns':'none','scope':'static gate/protocol review; no numeric or remote work','memo':'agents/G3_GATE_INDEPENDENT.md'},
        {'agent':'g3_statistics_design_review_20261114','model':'gpt-6.1-sol','reasoning_effort':'xhigh','fork_turns':'none','scope':'static statistical-design review; no numeric or remote work','memo':'agents/STATISTICAL_DESIGN_REVIEW.md'},
    ],
    'evidence': ['ANALYSIS_INTENT.json','results/SUMMARY.json','results/INDEPENDENT_AUDIT.json','results/ALL_REGISTERED_SEED_ROWS.csv','results/AUTHOR_ROWS.csv','results/CELL_SEED_SUMMARY.csv','results/MAP_METHOD_SUMMARY.csv','results/ALL_24_MAP_EFFECTS.csv','results/FAMILY_DESCRIPTIVE.csv','results/WIND_DESCRIPTIVE.csv','results/DEPLOYMENT_BASELINE_FREEZE.json','analysis_guard/TERMINAL.json','independent_audit_guard/TERMINAL.json','FINAL_LEDGER_RECHECK.json'],
    'resource_accounting': ledger,
    'user_decision_required': False,
}
save(A/'G3_ADJUDICATION.json', adjudication)

report = '''# 固定风性能汇总与 F3 G3 科学判定

本轮已经完成性能汇总、EXECUTION_HOST 独立原始记录数值审计和最终范围判定。此前完成的是实验终局核验；不能把此前“待汇总”记录改称当时已开始统计。

## 已证实事实

24 张独立底图、12 个固定几何族每族 2 图、3 个预定风 `(0,0)/(240,0)/(0,480)` m/min；72 个完整同风作者全部合格，2,880 条强控制全部按时有效。缺行、重复、失败和跳过均 0，ITT 与 valid-only 相同。所有运行 seed 保留；独立样本量为 24 图，运行 seed 和风不扩充独立 n。

主效应逐图先对三风和十个运行 seed 平均 `100×(1−M_return/M_author)`，再平均 24 图；等价于固定十二族等权。M_return 是含返航的完工时间，越小越好。每行完整覆盖、累计 duty、逐趟含返航电量、同风作者成本 cap +1e−7 和完整进程按时退出均按既有收据核对。

|强控制|6 秒相对作者平均降幅|12 秒相对作者平均降幅|两预算各自地图胜/平/负|
|---|---:|---:|---|
|原生强 ALNS|15.726630%|15.727271%|22/2/0；22/2/0|
|独立共同 H|12.958403%|14.861506%|21/3/0；22/2/0|

这些是给定共同完整作者锚点后的条件精修收益。作者生成在控制 6/12 秒之外，72 个作者生成和审计完整墙钟合计 1591.8223543264903 秒，Main 子进程 CPU 合计 1543.9629430000002 秒；不能解释为端到端同墙钟胜作者。

共同 H 减 ALNS 的作者归一化收益为：6 秒 −2.768227 个百分点，地图胜/平/负 4/6/14；12 秒 −0.865765 个百分点，8/7/9。八效应 Bonferroni 探索性区间分别为 [−4.726049, −0.790394] 和 [−2.430598, 0.702627] 个百分点。6 秒结果偏向 ALNS；12 秒数据尚不足以确立差异或等效。共同 H 增加预算的平均收益为 +1.903103 个百分点，ALNS 为 +0.000641 个百分点；不能据此断言 ALNS 已达全局最优或 RL 已有剩余空间。

每预算只冻结一个全局部署基线：6 秒和 12 秒均为原生强 ALNS。两强控制继续作为未来 RL 必比对象。没有逐图挑最好方法、best-of-10 主结论或削弱强 ALNS；自然提前停止完整保留。逐族、逐风、逐单元 seed 方差、全部 24 图效应、原始 2880 行、成本与完整进程时间见 results/。

## G3 最终判定

`F3_G3_QUALIFICATION_OPPORTUNITY_PASS_LIMITED_DOMAIN_WITH_INFERENCE_PREREG_DEVIATION`

已登记 F3 三风范围的完整作者资格、两强 nonRL 控制资格、可靠性分母、描述性机会和后续公平比较基础阶段完成。该阶段不要求 RL 先胜；没有事后添加 5% 或 0.3% 的 G3 门槛。独立协议代理和统计设计代理均采用 GPT-6.1-Sol / xhigh；仅 root 在 EXECUTION_HOST 执行数值。

保留统计预登记缺口：上游要求开放数据前冻结推断参数，实际执行冻结缺少这些数值设置。本轮 50,000 次分族地图 cluster bootstrap、seed 2026111419、八效应 Bonferroni 区间均是数据完成后指定，全部明确作为事后探索性区间。多重比较修正不把它们变成预注册确认性证据；每族只有两图，覆盖稳定性有限；未算 p 值。

本结论不等于全项目无条件 G3 总通过，不外推到 17 风或任意风域，不分解风速/方向主效应。原项目更广的随机/规则/greedy/beam/监督/BC/bandit/标准 RL 等比较族、同组件消融和新数据划分资格仍需按适用协议逐项完成。后续 DEV/Formal 必须用新身份，本批地图已暴露。

## 未证实假说

G0 学习增量仍未通过；AIR2 有限链通过但未改善完工时间。现有控制收益不是 RL 收益，也不证明后续前缀能产生首表之外的有效新路线。训练更新、模型、checkpoint 和 Formal 均为 0。没有据此宣布 RL 突破或 G8 完成。

## 失败或关闭方向

原 execution_v1 的整数/浮点风身份失败保持；recovery_v2 复用 24 图及成功 A000，未重跑它们。旧关闭候选和全部失败保留。本轮只处理已有结果，没有新增地图、作者或控制求解。最终账簿复查首次因早期事件缺少 row_id 读取失败，纯账簿脚本按既有混合 schema 修正后通过，首个失败另存 FINAL_LEDGER_RECHECK_FAILED1.json；科学结果、源码、账簿均未改动。

## 下一项有界工作

返回 G0，先对照既有 AIR2 设计与失败证据，冻结“后续物理前缀能否发现初始表外有效路线、学习能否优于同组件强控制”的具体可否证机制与最小资格计划。RL 仍只输出物理 `(slot,target)/(slot,RETURN)`，不选择算子或搜索预算。G0 及后续独立门槛未满足前不启动训练或 Formal；不在本批已暴露地图上调参。

## 是否需要用户决策

当前不需要。实验于北京时间 2026-11-14 17:53:52 已结束；本轮性能汇总和独立审计均退出 0、子孙清理通过，权威票据最后复查没有活动预算行。全票据保守扣账 17627.315978666 秒，约 4.896477 核时，低于已批 48 核时；原 300 秒保守预占保留，内层 ROW 账不重复相加。

## 证据与复用

- results/PERFORMANCE_SUMMARY_ZH.md、SUMMARY.json、INDEPENDENT_AUDIT.json：EXECUTION_HOST 数值与独立 fsum 核验。
- G3_ADJUDICATION.json：机器可读范围、结论和全部偏差。
- agents/G3_GATE_INDEPENDENT.md、STATISTICAL_DESIGN_REVIEW.md：两份独立静态审查。
- VERIFICATION.txt、LIFECYCLE_COMMANDS.json、analysis_guard/、independent_audit_guard/：真实命令、完整字面输出、退出与副本回滚收据。
- MODIFIED_FILE/aggregate.py 与 audit_results.py 可用于新的独立输出目录；本批成功分析不再重跑。分析 intent 为事后记录，不能改名充预注册。
'''
(A/'G3_ADJUDICATION_ZH.md').write_text(report)

state = read(P/'STATE.json')
state['status'] = 'PERFORMANCE_SUMMARY_AND_SCOPED_F3_G3_ADJUDICATION_COMPLETE_WITH_LIMITS'
state['G3'] = LABEL
state['project_wide_unconditional_G3_pass'] = False
state['performance_analysis'] = {'status':summary['status'],'independent_audit':audit['status'],'independent_maps':24,'control_rows':2880,'summary':'performance_g3_analysis_v1/results/SUMMARY.json','adjudication':'performance_g3_analysis_v1/G3_ADJUDICATION.json','confirmatory_inference_preregistration_satisfied':False,'new_solves':0}
state['cpu_guard'] = 'COMPLETED; ALL_TERMINAL; NO_ACTIVE_BUDGET_ROWS; 48_CORE_HOUR_CAP_RETAINED'
state['requested_task_status']['scientific_driver_budget_outer_timer_full_source_closure'] = 'INTEGRATED_AND_COMPLETED_WITH_TERMINAL_AUDIT_PASS'
state['requested_task_status']['performance_comparison_summary'] = 'COMPLETE_INDEPENDENT_ORIGINAL_RECORD_AUDIT_PASS'
state['requested_task_status']['F3_G3_scientific_adjudication'] = LABEL
state['conservative_total_debit_seconds'] = ledger['conservative_debit_seconds']
state['budget_accounting']['final_conservative_debit_seconds'] = ledger['conservative_debit_seconds']
state['budget_accounting']['final_conservative_debit_core_hours'] = ledger['conservative_debit_core_hours']
state['budget_accounting']['latest_recheck'] = 'performance_g3_analysis_v1/FINAL_LEDGER_RECHECK.json'
state['training_or_Formal_blockers'] = ['G0 RL learning increment not passed','Broader applicable comparator and fresh-split obligations not certified by scoped F3 G3','Training/Formal protocols and resource gates remain separate']
state['deployment_baseline_by_budget'] = {'6s':'native_strong_minmax_ALNS','12s':'native_strong_minmax_ALNS','both_registered_strong_controls_remain_mandatory':True,'selection_scope':'postcollection calibration; future DEV/Formal fresh identities'}
state['new_agents_spawned_or_resumed_this_continuation'] = 2
state['this_continuation_agent_configuration'] = {'model':'gpt-6.1-sol','reasoning_effort':'xhigh','fork_turns':'none','scope':'static local reviews only; root owns EXECUTION_HOST'}
state['next_bounded_work'] = 'G0 mechanism qualification design for later-prefix physical route generation and attributable learning increment; no new training/Formal admission'
state['background_scientific_task_running'] = False
state['as_of_utc'] = NOW
save(P/'STATE.json', state)
(P/'REPORT_ZH.md').write_text(report + '\n---\n\n## 历史记录：本轮性能分析前的终局核验报告\n\n' + (A/'ORIGINALS/REPORT_ZH.md').read_text())
latest = '''## 2026-11-14 最新：性能汇总与限定 F3 G3 判定已完成

本轮 root 在 EXECUTION_HOST 完成既有 24 图/72 作者/2880 强控制的性能汇总及独立原记录 fsum 核验；两项 guard 均 exit0、完整清理。无新增地图/求解/训练。两名新静态审查 agent 均显式 GPT-6.1-Sol / xhigh / fork_turns=none，数值和远端调度仍仅 root。下文“性能未汇总/G3待判定”是历史时点。

原生强 ALNS 相对完整作者锚点的平均 M_return 降幅：6s 15.726630%、12s 15.727271%；独立共同 H：12.958403%、14.861506%。均为给定完整作者解后的条件精修，作者生成成本在 6/12s 外。H−ALNS 为 −2.768227/−0.865765 个百分点；6s 探索区间偏向 ALNS，12s 区间跨零、不作等效结论。全局部署两预算均冻结原生强 ALNS，两强控制未来仍必比；没有逐图 oracle、best-of10 或弱化基线。全部 seed/风/族/24地图效应、成本和完整退出时间已导出。

已登记 F3 三风的 G3 作者/强nonRL资格及描述性机会阶段：`F3_G3_QUALIFICATION_OPPORTUNITY_PASS_LIMITED_DOMAIN_WITH_INFERENCE_PREREG_DEVIATION`。独立 n=24 图，非2880；bootstrap 数值设置事后指定，50,000重采样/八效应Bonferroni区间仅探索性，每族两图限制明确。统计预冻结缺口保留；不称全项目无条件G3、17风泛化、RL学习增量或Formal通过。G0未过，模型/训练/checkpoint/Formal仍0。

全票据最新保守扣账17627.315978666s，约4.896477核时/已批48核时，活动预算行0；原失败、300s预占、三保护STATE原SHA保持。首次最终账簿只读核查的混合schema错误保留，修正后通过，未影响科学数据。详见 joint_weather_emergency/20261114_f3_g3_authorized_v1/performance_g3_analysis_v1/G3_ADJUDICATION_ZH.md、G3_ADJUDICATION.json、VERIFICATION.txt 和 results/。下一项为G0具体物理路线学习机制的有界资格设计，不在暴露人口调参；当前无需用户操作或决策。

'''
(ROOT/'LATEST_STATUS.md').write_text(latest + (A/'ORIGINALS/LATEST_STATUS.md').read_text())
old_ledger = (P/'RESOURCE_LEDGER.jsonl').read_bytes()
final_ledger = (A/'RESOURCE_LEDGER_FINAL_RECHECK.jsonl').read_bytes()
assert final_ledger.startswith(old_ledger), 'Ledger snapshot must preserve the previous prefix'
(A/'ORIGINALS/RESOURCE_LEDGER.jsonl').write_bytes(old_ledger)
(P/'RESOURCE_LEDGER.jsonl').write_bytes(final_ledger)

commands = read(A/'LIFECYCLE_COMMANDS.json')
for phase, folder in [('MODIFIED', 'analysis_guard'), ('MODIFIED_INDEPENDENT_AUDIT', 'independent_audit_guard')]:
    terminal = read(A/folder/'TERMINAL.json')
    commands.append({'phase':phase,'command':terminal['command'],'cwd':terminal['cwd'],'input':'Existing registered FINAL_DELIVERY and author records only; no new solve','stdout_literal':(A/folder/'STDOUT.txt').read_text(),'stderr_literal':(A/folder/'STDERR.txt').read_text(),'exit_status':terminal['exit_status'],'terminal_receipt':folder+'/TERMINAL.json','budget_and_cleanup_pass':terminal['budget_and_cleanup_pass']})
save(A/'COMPLETE_COMMAND_EVIDENCE.json', commands)
verification = ['F3 G3 performance analysis and scoped adjudication — verified records',
    'Recorded at UTC: '+NOW,
    'Changed branch/field: top-level STATE.G3 SCIENTIFIC_ADJUDICATION_PENDING -> '+LABEL,
    'New source: aggregate.py and audit_results.py (previously absent); scientific solver/source closure unchanged.',
    'No new map/author/control solve, training, or Formal in this analysis.',
    'Scientific arithmetic ran on EXECUTION_HOST only; this finalizer performs document/byte/hash bookkeeping only.',
    'Original top-level hashes: '+json.dumps(intent['original_snapshot_hashes'],sort_keys=True),
    'Analysis intent SHA256: '+sha(A/'ANALYSIS_INTENT.json'),
    'SUMMARY SHA256: '+sha(A/'results/SUMMARY.json'),
    'Aggregate source SHA256: '+sha(A/'MODIFIED_FILE/aggregate.py'),
    'Independent audit source SHA256: '+sha(A/'MODIFIED_FILE/audit_results.py'),
    'Original 255-file scientific closure SHA256: 8a85a3d5dcf43476b9cc8016b4f81124e8a958320603c0937d7eb66c210879a3',
    'Four artifacts: '+json.dumps([str(A/'MODIFIED_FILE'),str(A/'DIFF_FILE.patch'),str(A/'VERIFICATION.txt'),str(A/'ROLLBACK.sh')]),
    'BASELINE/ROLLBACK below are metadata/source lifecycle proofs, not scientific ALNS baselines.',
    'Restored behavior/status in independent proof copy: original G3 pending bytes match; aggregate.py absent. Main analysis source and results remain present.',
    'Protected STATE hashes unchanged: '+json.dumps(protected,sort_keys=True),
    'Final resource bookkeeping: '+json.dumps(ledger,sort_keys=True),
    'The first mixed-schema ledger recheck failed KeyError(row_id), exit1, and is preserved in FINAL_LEDGER_RECHECK_FAILED1.json. Corrected read-only recheck exited0.',
    'Claim boundary: F3 qualification/opportunity only; posthoc exploratory CIs; G0 not passed; training/Formal 0.',
]
for c in commands:
    verification.extend(['\nPHASE: '+c['phase'], 'COMMAND: '+shlex.join(c['command']), 'CWD: '+c.get('cwd',REMOTE), 'INPUT: '+c['input'], 'STDOUT_LITERAL_BEGIN\n'+c['stdout_literal']+'STDOUT_LITERAL_END', 'STDERR_LITERAL_BEGIN\n'+c['stderr_literal']+'STDERR_LITERAL_END', 'EXIT_STATUS: '+str(c['exit_status'])])
(A/'VERIFICATION.txt').write_text('\n'.join(verification)+'\n')

docdiff = ''
for name, target in [('STATE.json',P/'STATE.json'), ('REPORT_ZH.md',P/'REPORT_ZH.md'), ('LATEST_STATUS.md',ROOT/'LATEST_STATUS.md')]:
    docdiff += ''.join(difflib.unified_diff((A/'ORIGINALS'/name).read_text().splitlines(keepends=True),target.read_text().splitlines(keepends=True),fromfile='ORIGINALS/'+name,tofile=str(target.relative_to(ROOT))))
(A/'DOCUMENT_STATE_DIFF.patch').write_text(docdiff)
files = [p for p in A.rglob('*') if p.is_file() and p.name not in ['FINAL_ARTIFACT_MANIFEST.json','FINAL_READBACK.json']]
manifest = [{'path':str(p.relative_to(A)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(files)]
save(A/'FINAL_ARTIFACT_MANIFEST.json', manifest)
for row in manifest:
    assert sha(A/row['path']) == row['sha256']
for rel, expected in protected.items():
    assert sha(ROOT/rel) == expected
assert read(P/'STATE.json')['G3'] == LABEL
assert read(P/'STATE.json')['training_updates'] == read(P/'STATE.json')['Formal'] == 0
assert '已完成' in (ROOT/'LATEST_STATUS.md').read_text()[:90]
assert (A/'G3_ADJUDICATION_ZH.md').read_text() == report
assert all(c['exit_status']==0 for c in commands)
readback={'status':'FINAL_DOCUMENTS_AND_MANIFEST_REOPENED_PASS','created_utc':NOW,'adjudication':LABEL,'artifact_files_reopened':len(manifest),'protected_states_unchanged':True,'top_state_sha256':sha(P/'STATE.json'),'latest_status_sha256':sha(ROOT/'LATEST_STATUS.md'),'report_sha256':sha(P/'REPORT_ZH.md'),'summary_sha256':sha(A/'results/SUMMARY.json'),'new_scientific_runs':0,'models':0,'training_updates':0,'Formal':0,'user_decision_required':False}
save(A/'FINAL_READBACK.json',readback)
assert read(A/'FINAL_READBACK.json')==readback
print(json.dumps(readback,ensure_ascii=False,sort_keys=True))
