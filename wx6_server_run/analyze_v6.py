#!/usr/bin/env python3
"""v6 final analysis (PREREG_v6 sec. 7, order fixed):
 (0) structural gate of all plan sets (Omega coverage, official feasibility, #DABS, fixed cost, TSALNS-Cov repairs)
 (1) strict completion gate (all arms, all tests)            -> any arm < 100 % is flagged (dagger), not interpreted
 (2) H1  Test-M: RL6 (5-seed mean) vs every realisable baseline on J5, Holm over baselines
 (3) H2  Test-M: RL6 vs SB on OT, late_h, late_n, fails, Holm(4)  (superiority)
 (4) per-seed confirmation vs SB (J5 and OT); main claim needs >= 4/5 seeds confirmed on J5
 (5) secondary metrics vs all baselines (cost, ontime_h, n_backup), Holm
 (6) ablations (own Holm family)
 (7) generalisation Test-G / Test-L; robustness scenarios; siting variants (TSR, PAD, TSC-r10)
 (8) latency classes (rollouts, 20-day subset), window sensitivity, weight sensitivity, appendix makespan
Outputs: results_final/SUMMARY_ZH.md, ANALYSIS_V6.json, raw_compact.csv (every row, compact fields)."""
import os, sys, json, glob, datetime
from collections import defaultdict
import numpy as np
ROOT = os.environ.get("WX_ROOT", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from v6 import fairproto as FP

RES = os.path.join(ROOT, "results"); OUT = os.path.join(ROOT, "results_final")
os.makedirs(OUT, exist_ok=True)
L = []
J = {}


def P(s=""):
    L.append(s)


def fmt(x, d=1):
    return "—" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{d}f}"


def mean(t, m, k):
    v = [r.get(k, 0.0) for r in t.get(m, {}).values()]
    return float(np.mean(v)) if v else float("nan")


def load_json(p, default=None):
    try:
        return json.load(open(p))
    except Exception:
        return default


SB = (load_json(os.path.join(RES, "SB_FREEZE.json"), {}) or {}).get("SB", "")
N6B = (load_json(os.path.join(RES, "N6_FREEZE.json"), {}) or {}).get("best", "N6_90_0.25")
MAIN = "RL6"
SEEDP = {"RL6_s": "RL6", "RL6noES_s": "RL6noES", "RL6nf_s": "RL6nf", "RL6ne_s": "RL6ne", "RL6uc_s": "RL6uc",
         "RL6ns_s": "RL6ns"}
ABL = [("RL6noES", "无 ES 微调（仅蒸馏）"), ("RL6nf", "无天气预报特征"), ("RL6ne", "无紧急任务特征"),
       ("RL6uc", "无加班约束（仅 C_OT 计价）"), ("RL6ns", "无班次护盾"), ("RL5", "v5 派遣层（上一版本）"), ("SB", "最强非 RL 基线")]
SEC = [("cost", -1), ("ontime_h", 1), ("n_backup", -1), ("cvar_h", -1)]
H2M = [("ot_min", -1, "加班"), ("late_min_h", -1, "高优迟到"), ("late_min_n", -1, "普通迟到"), ("fails", -1, "失败")]
COLS = [("J", "J5", 1), ("cost", "成本", 1), ("ot_min", "加班", 1), ("fails", "失败", 2), ("late_min_h", "高优迟到", 1),
        ("late_min_n", "普通迟到", 1), ("ontime_h", "高优准时", 3), ("n_backup", "备用机", 3), ("ms_p99", "p99 ms", 2),
        ("mk", "完工(附录)", 1), ("complete_strict", "严格完成", 4)]


def prep(rows, plan_set, scenario):
    t = FP.table(rows, plan_set=plan_set, scenario=scenario)
    seeds = {}
    for pref, nm in SEEDP.items():
        ss = FP.seed_mean(t, pref, nm)
        if ss:
            seeds[nm] = ss
    return t, seeds


def metric_table(t, methods, title):
    P(f"\n**{title}**\n")
    P("| 方法 | " + " | ".join(c[1] for c in COLS) + " | n |")
    P("|---|" + "---|" * (len(COLS) + 1))
    for m in methods:
        if m not in t or not t[m]:
            continue
        cs = mean(t, m, "complete_strict"); dag = "" if cs >= 1 - 1e-12 else " †"
        P(f"| {m}{dag} | " + " | ".join(fmt(mean(t, m, c[0]), c[2]) for c in COLS) + f" | {len(t[m])} |")


def fam_table(res, title):
    P(f"\n**{title}**\n")
    P("| A | B | 指标 | A 均值 | B 均值 | 相对差% | 交叉CI | 图胜/负 | p | p_Holm | p_day | 确认 |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res:
        P(f"| {r['a']} | {r['b']} | {r['metric']} | {fmt(r['mean_a'],2)} | {fmt(r['mean_b'],2)} | {r['rel']:+.2f} | "
          f"[{r['ci'][0]:+.2f}, {r['ci'][1]:+.2f}] | {r['map_win']}/{r['map_lose']} | {r['p']:.2e} | {r.get('p_holm', float('nan')):.2e} | "
          f"{r['p_day']:.2e} | {'✓' if r.get('confirmed') else ('✗更差' if r.get('confirmed_worse') else '—')} |")


def baselines_in(t):
    pref = ["A1", "A2", "N1_240", "N6_best", "S:N6_best", "R_N6best", "Rfc_N6best", "RfcP_N6best", "S:RfcP_N6best", "RL5"]
    out = [b for b in pref if b in t and t[b]]
    if "SB" in t and t["SB"]:
        out.append("SB")
    return out


def section_test(rows, title, plan_set, scenario, primary=False, key=""):
    t, seeds = prep(rows, plan_set, scenario)
    if MAIN not in t:
        P(f"\n### {title}: 无 RL6 结果（未运行）"); return None
    allm = list(t)
    g = FP.gate(t, allm)
    P(f"\n### {title}（plan_set={plan_set}, scenario={scenario}）")
    P("\n严格完成率门槛（†=未达 100%，该臂其余指标不作解读）：")
    P("| 方法 | n | 严格完成率 | 未完成单元 | 不可覆盖请求合计 | 通过 |")
    P("|---|---|---|---|---|---|")
    for m in sorted(allm):
        P(f"| {m} | {g[m]['n']} | {g[m]['complete_strict']:.4f} | {g[m]['n_incomplete']} | {g[m]['n_unservable_all']} | {'✓' if g[m]['passed'] else '✗'} |")
    par = {b: FP.check_parity(t, MAIN, b) for b in baselines_in(t)}
    P("\n选址一致性（RL6 与每个基线执行同一份计划；#DABS 与固定成本逐单元相同）：" +
      ("全部一致 ✓" if all(v["ok"] for v in par.values()) else f"不一致！{par}"))
    order = [MAIN] + sorted(seeds.get(MAIN, [])) + baselines_in(t) + [m for m, _ in ABL if m in t and m not in ("SB", "RL5")] + \
            [m for m in t if m.startswith(("RL6R", "N4fd", "O"))]
    seen = []; [seen.append(m) for m in order if m not in seen]
    metric_table(t, seen, "主要与次要指标（均值；n=地图×天）")
    bases = baselines_in(t)
    out = dict(gate=g, parity=par, sb=SB)
    h1 = FP.family(t, MAIN, bases, "J", -1); fam_table(h1, "H1：RL6（5 种子均值）vs 全部可实现基线，J5，Holm"); out["H1"] = h1
    if "SB" in t:
        h2 = []
        for mtr, b, _ in H2M:
            h2.append(FP.compare(t, MAIN, "SB", mtr, b))
        adj = FP.holm([r["p"] for r in h2])
        for r, pa in zip(h2, adj):
            r["p_holm"] = float(pa); good = r["rel"] * r["better"] > 0
            sig = pa < 0.05 and r["p_day"] < 0.05 and (r["ci"][0] > 0 or r["ci"][1] < 0)
            r["confirmed"] = bool(sig and good); r["confirmed_worse"] = bool(sig and not good)
        fam_table(h2, f"H2：RL6 vs SB（{SB}）的加班 / 迟到 / 失败，Holm(4)"); out["H2"] = h2
        ps = []
        for s in seeds.get(MAIN, []):
            rj = FP.compare(t, s, "SB", "J", -1); ro = FP.compare(t, s, "SB", "ot_min", -1)
            ps.append((s, rj, ro))
        if ps:
            adj = FP.holm([x[1]["p"] for x in ps])
            P(f"\n**逐种子 vs SB（{SB}）**（J5 的 Holm 按种子数校正）\n")
            P("| 种子 | J5 相对差% | 交叉CI | p_Holm | p_day | 确认 | 加班相对差% | 加班CI |")
            P("|---|---|---|---|---|---|---|---|")
            nconf = 0
            for (s, rj, ro), pa in zip(ps, adj):
                c = pa < 0.05 and rj["p_day"] < 0.05 and rj["ci"][1] < 0
                nconf += c
                P(f"| {s} | {rj['rel']:+.2f} | [{rj['ci'][0]:+.2f}, {rj['ci'][1]:+.2f}] | {pa:.2e} | {rj['p_day']:.2e} | {'✓' if c else 'n.s.'} | "
                  f"{ro['rel']:+.2f} | [{ro['ci'][0]:+.2f}, {ro['ci'][1]:+.2f}] |")
            P(f"\n确认的种子数：{nconf}/{len(ps)}（预注册要求 ≥ 4/5）")
            out["per_seed"] = dict(n_confirmed=int(nconf), n=len(ps))
    if primary:
        sec = []
        for mtr, b in SEC:
            sec += FP.family(t, MAIN, bases, mtr, b)
        adj = FP.holm([r["p"] for r in sec])
        for r, pa in zip(sec, adj):
            r["p_holm"] = float(pa)
        fam_table(sec, "次要指标（cost / ontime_h / 备用机 / CVaR90），Holm（整族）"); out["secondary"] = sec
        ab = [(m, d) for m, d in ABL if m in t and t[m]]
        if ab:
            res = FP.family(t, MAIN, [m for m, _ in ab], "J", -1)
            fam_table(res, "消融（J5，Holm）：" + "；".join(f"{m}={d}" for m, d in ab)); out["ablation"] = res
        # weight sensitivity (re-scored, no retraining)
        P("\n**惩罚权重敏感性（只重计分）：RL6 vs SB 的 J5 相对差%**\n")
        P("| 权重 | RL6 | SB | 相对差% |"); P("|---|---|---|---|")
        for nm, w in [("C_OT=0", dict(ot=0)), ("C_OT=2", dict(ot=2)), ("C_OT=4", dict(ot=4)), ("P×0.5", dict(P=50)),
                      ("P×2", dict(P=200)), ("lateH×0.5", dict(lh=15)), ("lateH×2", dict(lh=60))]:
            ww = dict(ot=1, lh=30, ln=10, P=100); ww.update(w)
            def rs(m):
                return float(np.mean([r["cost"] + ww["ot"] * r["ot_min"] + ww["lh"] * r["late_min_h"] + ww["ln"] * r["late_min_n"]
                                      + ww["P"] * r["fails"] for r in t[m].values()]))
            if "SB" in t:
                a, b = rs(MAIN), rs("SB"); P(f"| {nm} | {a:.1f} | {b:.1f} | {(a-b)/b*100:+.2f} |")
    if key:
        J[key] = out
    return out


def structural():
    P("\n## 0. 计划结构门槛（Ω 覆盖、官方可行性、#DABS、固定成本）\n")
    P("| 计划集 | 计划数 | 可行 | Ω 未覆盖的计划 | TSALNS-Cov 修复次数 | 平均 #DABS | 平均开站数 | 平均固定成本 | 平均静态成本 |")
    P("|---|---|---|---|---|---|---|---|---|")
    st = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "plans6", "*.jsonl"))):
        rr = [json.loads(l) for l in open(f) if l.strip()]
        if not rr:
            continue
        nm = os.path.basename(f)[:-6]
        from v6.common import read_instance, fixed_cost
        from v6 import cover as CV
        unc = 0
        for r in rr:
            ins = read_instance(os.path.join(ROOT, r["path"]))
            unc += CV.n_uncovered(ins, r["solution"]["station_types"]) > 0
        d = dict(n=len(rr), feasible=int(sum(1 for r in rr if r.get("feasible", True))), uncovered=int(unc),
                 repaired=int(sum(r.get("cover_info", {}).get("repaired", 0) for r in rr)),
                 n_dabs=float(np.mean([sum(1 for t in r["solution"]["station_types"] if t == 2) for r in rr])),
                 n_open=float(np.mean([sum(1 for t in r["solution"]["station_types"] if t > 0) for r in rr])),
                 fixed=float(np.mean([fixed_cost(r["solution"]["station_types"]) for r in rr])),
                 cost=float(np.mean([r.get("cost") or 0.0 for r in rr])))
        st[nm] = d
        P(f"| {nm} | {d['n']} | {d['feasible']} | {d['uncovered']} | {d['repaired']} | {d['n_dabs']:.2f} | {d['n_open']:.2f} | {d['fixed']:.1f} | {d['cost']:.1f} |")
    J["structural"] = st


def main():
    files = sorted(glob.glob(os.path.join(RES, "*.jsonl")))
    rows = FP.load_rows([f for f in files if not os.path.basename(f).startswith(("dev_", "win_", "lookahead"))])
    allrows = FP.load_rows([f for f in files if not os.path.basename(f).startswith("dev_")])
    FP.export_csv(allrows, os.path.join(OUT, "raw_compact.csv"))
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    P(f"# WX6 结果汇总（自动生成 {now}；预注册 PREREG_v6.md）\n")
    P(f"- 冻结：N6_best = `{N6B}`；最强非 RL 基线 SB = `{SB}`（dev 上按严格完成率 100% + J5 最小选出）")
    P(f"- 原始逐例数据：`raw_compact.csv`（{len(rows)} 行；字段见 v6/fairproto.py COMPACT），可独立复算全部统计")
    structural()
    P("\n## 1–6. 主测试 Test-M（Liu 50 图 × 100 新天，作者适配计划 TSALNS-Cov）")
    section_test(rows, "Test-M", "test_tsc", "base", primary=True, key="TestM")
    P("\n## 7. 泛化 / 稳健性 / 选址变体")
    section_test(rows, "Test-G（100 张新图 × 30 天）", "fresh6_tsc", "base", key="TestG")
    section_test(rows, "Test-L（30 张大图 × 30 天）", "large6_tsc", "base", key="TestL")
    for sc in ("stress", "sigma15", "ncbias6", "uniform"):
        section_test(rows, f"稳健性 {sc}（Test-M 地图 × 50 天）", "test_tsc", sc, key=f"R_{sc}")
    for ps, d in (("test_tsr", "TSR：作者原版 TSALNS + 精确最小成本覆盖修复"), ("test_pad", "PAD：全部候选站开为 DABS"),
                  ("test_tscr10", "TSALNS-Cov + 10% 电量预留")):
        section_test(rows, f"选址变体 {d}", ps, "base", key=f"S_{ps}")
    P("\n## 8. 时延分级 / 作业窗口 / 附录")
    for w in ("ot180", "ot300"):
        rw = [r for r in FP.load_rows([os.path.join(RES, f"win_{w}.jsonl")])]
        if rw:
            section_test(rw, f"作业窗口 {w}", "test_tsc", "base", key=f"W_{w}")
    rl = FP.load_rows([os.path.join(RES, "lookahead.jsonl")])
    if rl:
        t = FP.table(rl, plan_set="test_tsc", scenario="base")
        metric_table(t, sorted(t), "look-ahead 类（100 ms 截止的公平滚动；20 天子集；O 为全知参照，不参与检验）")
        if "RL6R_100ms" in t and "N4fd_100ms" in t:
            fam_table(FP.family(t, "RL6R_100ms", ["N4fd_100ms"] + [m for m in t if m.startswith("RL6_s")][:1], "J", -1), "RL6R vs 同时延滚动基线")
    open(os.path.join(OUT, "SUMMARY_ZH.md"), "w").write("\n".join(L) + "\n")
    json.dump(J, open(os.path.join(OUT, "ANALYSIS_V6.json"), "w"), indent=1, default=str)
    print("[analyze_v6] wrote results_final/SUMMARY_ZH.md, ANALYSIS_V6.json, raw_compact.csv")


if __name__ == "__main__":
    main()
