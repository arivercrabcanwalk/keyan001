# WX-E 服务器实验包（pomo_v2）

把本目录放到 40 核服务器上，跑完剩余的 WX-E 实验：种子 1、2 的正式训练，以及 Test-A、P3、P4、价值网络和 WX-H。

- 只用**合成天气**（σ0=1 m/s，κ=0.5 m/s/h，**不是** ERA5）。
- 训练协议与预注册一致（见 `wx_e/PREREG.md`，含 pomo_v2 附录）：BC 3 epoch → DAgger 2 轮（M=8，200 天）→ 2 小时 POMO v2，K=8，B=24。
- **种子 0 已完成**（本机正式结果：G-b 通过，G-c 未通过），检查点和 `wx_e/GB_s0_pomo_v2.json` 已放在包里，不会重训。
- **种子 1、2 从零开始**训练（完整 BC + 两轮 DAgger + 2 小时 POMO）。种子 1 没有接着本机做到一半的 DAgger r1 往下跑，这样可复现、也符合预注册。
- 网络是 numpy Adam，**不需要 GPU，也不需要 PyTorch**。
- 40 核、200 GB 内存上，预计墙钟 **7–10 小时**（两种子并行训练约 3–3.5 小时，其中含 2 小时 POMO 预算；下游 Test-A / P3 均匀故障重训 / P4 / 价值网络 / WX-H 约 4–6 小时，P3 重训与评估会重叠）。

---

## 操作步骤

### 1. 克隆仓库

仓库可能是私有的。请用**你自己的** GitHub 令牌（GitHub → Settings → Developer settings → Personal access tokens，勾选 `repo` 权限）。不要使用别人发给你的令牌，也不要把令牌写进代码或提交到仓库。

```bash
# 若仓库是公开的：
git clone https://github.com/arivercrabcanwalk/keyan001.git

# 若仓库是私有的，把 YOUR_TOKEN 换成你自己的令牌（命令跑完后，建议在 GitHub 上轮换该令牌）：
git clone https://YOUR_TOKEN@github.com/arivercrabcanwalk/keyan001.git
```

### 2. 进入目录

```bash
cd keyan001/wx2_server_run
```

### 3. 安装依赖

```bash
bash setup.sh
```

这一步会建 `.venv`，并在镜像里还没有 numpy / scipy 时再安装。如果镜像已经带了这两个包，会直接通过。

### 4. 启动全部实验

```bash
nohup bash run_all.sh > run_all.log 2>&1 &
```

请确认当前目录就是 `wx2_server_run`。脚本会：

1. 并行训练种子 1 和 2（把大约 38 个核均分给两个种子）；
2. 写出与预注册相同逻辑的 `wx_e/GB_s1_pomo_v2.json`、`wx_e/GB_s2_pomo_v2.json`（G-b / G-c）；
3. 自动跑下游：Test-A（Liu-50 × 天气日 7000–7029，只跑一次）、P3（均匀空间故障评估 + 种子 0 按 pomo_v2 重训 + ≥70% 风暴日增益份额）、P4（σ×1.5 与单体速度 +30%）、价值网络（含随机价值网络对照）、WX-H（1 / 10 / 100 ms）；
4. 写 `PROGRESS_SERVER.md` 和 `results_final/`；
5. 打包 `results_out.tar.gz`。

若至少 2/3 个种子同时通过 G-b 和 G-c，Test-A 记为官方；否则仍会跑一遍，但在结果里标明「非官方」，不得当作预注册正式 test。P3、P4、WX-H 无论闸门如何都会做（预注册写明：闸门失败时仍做有意义的 P3 与 WX-H，并如实记录）。

### 5. 查看进度

```bash
# 总进度（东京时间 Asia/Tokyo，UTC+9）
cat PROGRESS_SERVER.md

# 实时日志
tail -f run_all.log

# 单个种子的训练日志
tail -f logs/train_s1.out
tail -f logs/train_s2.out
```

某一种子结束后，对应的 `wx_e/GB_s{1,2}_pomo_v2.json` 会出现。三种子齐了会写 `wx_e/GB_V2_TALLY.json`。

### 6. 取回结果

全部结束后，本目录下会有：

- `results_out.tar.gz` — 请把这个文件下载下来发回（JupyterLab 右键下载即可）。
- `results_final/SUMMARY_ZH.md` — 中文汇总（G-b / G-c、P3、P4、WX-H、Test-A 是否官方）。

**默认不会向 GitHub 推送结果。** 若你希望脚本把结果提交并推回仓库：先在这台服务器上用**你自己的** git 凭据登录（`git config` 与 `git credential`，不要把令牌写进脚本），然后：

```bash
# 先配置好凭据，再设这个变量后重新打包推送时，可手动：
#   WX_PUSH_RESULTS=1 bash -c 'source /dev/null; # 见 run_all.sh 末尾 maybe_push'
```

更简单的做法：实验是在 `run_all.sh` 启动时读 `WX_PUSH_RESULTS`。若要自动推送，启动前执行：

```bash
export WX_PUSH_RESULTS=1
nohup bash run_all.sh > run_all.log 2>&1 &
```

仍须事先在本机配好你自己的 git 用户和凭据。脚本不会使用、也不会写入任何预置令牌。

---

## 其它说明

- 天气日缓存写在 `data/days/`，脚本会自动生成，不必事先准备；不要把 `.pkl` 提交到 git。
- 中途断了再跑 `bash run_all.sh` 是安全的：已有 `GB_s*_pomo_v2.json` 的种子会跳过，评估脚本会按 jsonl 已完成的行续跑。
- 冒烟（开发用，不是正式实验）：`SMOKE=1 bash run_all.sh`，几分钟内走完整条流水线。
- 本包不修改你原来的项目文件，只在 `wx2_server_run/` 里工作。
