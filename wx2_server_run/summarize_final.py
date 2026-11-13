#!/usr/bin/env python3
"""Write results_final/SUMMARY_ZH.md from GB files, tallies, and analyses."""
from __future__ import annotations
import os, sys, json, time
from pathlib import Path

ROOT = Path(os.environ.get("WX_ROOT") or Path(__file__).resolve().parent)


def jst():
    os.environ.setdefault("TZ", "Asia/Tokyo")
    time.tzset()
    return time.strftime("%Y-%m-%d %H:%M:%S JST")


def load(p):
    p = Path(p)
    if not p.exists():
        return None
    if p.suffix == ".json":
        return json.loads(p.read_text())
    return p.read_text()


def main():
    outdir = ROOT / "results_final"
    outdir.mkdir(exist_ok=True)
    lines = [f"# WX-E 服务器实验汇总\n\n写于 {jst()}。合成天气（σ0=1，κ=0.5，非 ERA5）。\n\n"]
    tally = load(ROOT / "wx_e" / "GB_V2_TALLY.json")
    lines.append("## 三种子 G-b / G-c（pomo_v2）\n\n")
    n_pass = 0
    n_done = 0
    for s in (0, 1, 2):
        g = load(ROOT / "wx_e" / f"GB_s{s}_pomo_v2.json")
        if not g:
            lines.append(f"- 种子 {s}：尚无正式结果。\n")
            continue
        n_done += 1
        gb, gc = bool(g.get("G_b")), bool(g.get("G_c"))
        if gb and gc:
            n_pass += 1
        lines.append(
            f"- 种子 {s}：G-b={'通过' if gb else '未通过'}（J={g.get('dev_J')}，"
            f"对 N1 ΔJ={g.get('gap_vs_bestN')}%，准时率 Δ={g.get('d_ot_pp')} pp；"
            f"G_b_J={g.get('G_b_J')} G_b_ot={g.get('G_b_ot')}）；"
            f"G-c={'通过' if gc else '未通过'}（KL={g.get('KL')}，动作差={g.get('frac_diff')}，"
            f"门槛 KL>0.01 且动作差≥5%）。\n"
        )
    official = n_pass >= 2 and n_done >= 3
    lines.append(f"\n通过 {n_pass}/{n_done}。官方 Test-A 解冻条件是至少 2/3 同时通过 G-b 和 G-c："
                 f"{'满足' if official else '不满足'}。\n")
    if tally:
        lines.append(f"Tally 文件：{json.dumps(tally, ensure_ascii=False)}\n")
    lines.append("\n种子 0 是本机 2 worker、2 小时预算的正式结果（已随包附带）。"
                 "种子 1、2 在本服务器上按预注册协议从零训练（完整 BC + 两轮 DAgger M=8 + 2 小时 POMO v2），"
                 "没有从本机未完成的 DAgger r1 热启动，以保证可复现、与预注册一致。\n\n")

    def add_md(title, path):
        p = ROOT / path
        if p.exists():
            lines.append(f"## {title}\n\n")
            lines.append(p.read_text())
            lines.append("\n")
        else:
            lines.append(f"## {title}\n\n文件不存在：`{path}`。\n\n")

    add_md("P3", "results_final/P3_ANALYSIS.md")
    add_md("P4", "results_final/P4_ANALYSIS.md")
    wxh = ROOT / "wx_h" / "WXH.md"
    if wxh.exists():
        lines.append("## WX-H\n\n")
        lines.append(wxh.read_text())
        lines.append("\n")
        summ = load(ROOT / "wx_h" / "WXH_SUMMARY.json")
        if summ:
            lines.append("```json\n" + json.dumps(summ, indent=2, ensure_ascii=False) + "\n```\n\n")
    else:
        lines.append("## WX-H\n\n尚未产出。\n\n")

    # Test-A official flag
    st = load(ROOT / "wx_e" / "results" / "testA_STATS.json")
    if st:
        lines.append("## Test-A\n\n")
        lines.append(f"- official={st.get('official')}  plans={st.get('plans')}  "
                     f"n_days={st.get('n_days')}  n_maps={st.get('n_maps')}\n")
        means = st.get("means") or {}
        for m, v in means.items():
            lines.append(f"- `{m}`：{json.dumps(v, ensure_ascii=False)}\n")
        if not st.get("official"):
            lines.append("\n**本次 Test-A 为非官方**（闸门未满 2/3），数字仅供诊断，不得当作预注册正式 test。\n")
        lines.append("\n")

    lines.append("## 文件位置\n\n")
    lines.append("- 闸门：`wx_e/GB_s*_pomo_v2.json`、`wx_e/GB_V2_TALLY.json`\n")
    lines.append("- 评估：`wx_e/results/`\n")
    lines.append("- 分析：`results_final/`\n")
    lines.append("- 模型：`models/rl_s*_best_pomo_v2.npz`\n")
    lines.append("- 打包：`results_out.tar.gz`\n")
    (outdir / "SUMMARY_ZH.md").write_text("".join(lines), encoding="utf-8")
    print("wrote", outdir / "SUMMARY_ZH.md")
    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
