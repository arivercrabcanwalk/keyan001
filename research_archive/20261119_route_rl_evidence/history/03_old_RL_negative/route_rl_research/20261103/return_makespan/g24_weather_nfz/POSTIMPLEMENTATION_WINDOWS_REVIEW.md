# Windows 运行路径与可重复性独立复核

**复核时间：** 2026-11-04（Asia/Shanghai）  
**范围：** `WINDOWS_RUNBOOK.md`、`REMOTE_EXECUTION_STATUS.md`、`run_full_map_smoke.py`、当前用户 SSH 配置，以及仅在本机完成的静态/基线检查。未修改实现代码、未启动远端进程、未生成研究地图或训练结果。

## 结论

Windows 端本次仍不可达，因此没有 Windows 测试、Windows checkpoint 或远端实验结果。现有运行清单可在**指定工作目录、普通（非 `-I`）Python 解释器**下找到源码；但它尚不足以支持干净 Windows 环境的可重复执行。阻断因素是依赖和解释器未冻结、源码布局未封装且脚本以固定父目录寻址、以及运行产物未自动记录环境/源码身份。以下修复完成并在 Windows 复验前，合成烟雾只能作为本机工程记录。

## SSH 实测

本机配置将 `windows` 解析为 `12198@<NETWORK_ADDRESS>`，经 `ProxyJump lighthouse`；`windows-lan` 解析为 `<EMAIL_REMOVED>`。没有改动 SSH 配置或建立转发。

| 命令 | 文字结果 | exit | 判定 |
|---|---|---:|---|
<CONNECTION_COMMAND_REMOVED>
<CONNECTION_COMMAND_REMOVED>
<CONNECTION_COMMAND_REMOVED>

该结果精确复现 `REMOTE_EXECUTION_STATUS.md:8-11` 的隧道拒绝和 mDNS 失败。它不提供任何远端 Python、PyTorch、CUDA、GPU 或实验状态；远端结果计数仍为零。

## 已核验的本机事实

1. 在 macOS 本机、普通解释器和当前 `g24_weather_nfz` 工作目录，运行清单的测试命令实际返回 exit 0：

   ```text
   PYTHONDONTWRITEBYTECODE=1 python -m unittest -v test_weather_oracle.py test_weather_pipeline.py test_rl_algorithms.py test_weather_full_map.py
   ...
   Ran 29 tests in 1.044s
   OK
   ```

   这不是 Windows 验收。该本机解释器为 Python `3.13.12`、NumPy `2.5.2`、PyTorch `2.12.1`、`torch.cuda.is_available() == False`。

2. 以隔离模式仅导入烟雾脚本成功：

   ```text
   PYTHONDONTWRITEBYTECODE=1 python -I -c 'import runpy; ns=runpy.run_path("run_full_map_smoke.py", run_name="__review_import__"); print("IMPORT_OK", ns["PACKAGE_ROOT"], ns["LUNWEN_ROOT"], ns["SEEDS"])'
   IMPORT_OK <LOCAL_PATH> <LOCAL_PATH> (103, 211, 307)
   ```

   但同一隔离解释器执行 `python -I -m unittest ...` 对四个测试模块均报 `ModuleNotFoundError`，因为 `-I` 不将当前目录留在 `sys.path`，而测试文件没有统一 bootstrap。这不影响运行清单的普通 `python -m unittest ...` 命令，仍说明该测试入口不能宣称支持 isolated mode。

3. 已有本机产物 `full_map_smoke_20261104/full_map_smoke_report.json` 记录了 3 个 PPO 和 3 个 A2C seed（103/211/307），每个 `complete: true`，命令为本机绝对 Python 路径，elapsed 为 `33.9131042920053` 秒。它的 scope 明确为 synthetic engineering fixture，不能替代 Windows 或研究地图证据。

4. 审查时仓库没有任何 `requirements*.txt`、`pyproject.toml`、lockfile 或 Conda environment 文件；`git rev-parse HEAD` 失败，原因是当前仓库尚无 commit，所有项目文件均为 untracked。因此不能由 commit ID 或依赖锁复原此次本机结果。

## 路径和依赖审查

| 风险 | 证据 | 影响 | 精确修复建议 |
|---|---|---|---|
| 未锁定解释器和 wheel | `WINDOWS_RUNBOOK.md:6` 使用无上界的 `py -3`；`:9` 为 `pip install numpy torch`；仓库没有依赖清单。 | Windows 的 Python minor、NumPy、PyTorch CPU/CUDA wheel 会随执行日期变动。 | 冻结经 Windows 验收的解释器 minor（例如锁定后使用 `py -3.X -m venv .venv`，不可继续使用 `py -3`）；提交 `requirements-windows.lock`，固定每个版本、wheel index 和 `--require-hashes`。运行时仅执行 `python -m pip install --require-hashes -r requirements-windows.lock`。 |
| 运行依赖未封装的目录关系 | `run_full_map_smoke.py:20-25` 假设 `PACKAGE_ROOT.parents[3]` 是 `lunwen`，并从其 `reproduction/reviewer_package_semfix` 导入 `lrphsd`；`weather_full_map.py:18-23` 又从 `PACKAGE_ROOT.parent` 导入 `scorer.py`。 | 仅复制 `g24_weather_nfz` 或改变层级会产生 `ModuleNotFoundError` 或导入另一份同名 `lrphsd`。 | 在 Windows 部署前封存完整目录树，至少保留 `g24_weather_nfz/`、其父目录的 `scorer.py`、以及项目根的 `reproduction/reviewer_package_semfix/lrphsd/`；在 runbook 开头显式 `Set-Location` 到 `g24_weather_nfz` 并对这三个路径执行 `Test-Path`。长期修复应把这些模块安装为一个受锁定的 Python package，移除 `sys.path` 和 `parents[3]` 假设。 |
| 同名历史副本容易被误导入 | 当前工程内可找到多份 `lrphsd/problem.py`；脚本只靠其手工 `sys.path` 顺序选定 semfix 副本。 | 复制或从错误目录执行时可能使用非 semfix 实现，却仍生成格式正常的输出。 | 将导入来源和 SHA-256 写入每次报告；运行前要求 `python -c` 打印 `lrphsd.problem.__file__` 与 `scorer.__file__`，并与冻结 manifest 比较。 |
| 输出目录可静默覆盖 | `run_full_map_smoke.py:128-163` 的 `mkdir(..., exist_ok=True)` 后无条件覆盖 6 个 `.pt` 和 JSON。 | 重跑会破坏先前证据，无法区分两个环境/依赖组合。 | 脚本应在 output dir 非空时失败，或 runbook 必须创建唯一 run ID 目录并在运行前拒绝已存在目录。 |
| 环境身份只由人工要求、未随报告固化 | `WINDOWS_RUNBOOK.md:14` 说要保留版本/GPU/stdout-stderr；`run_full_map_smoke.py:149-162` 未记录 Python、平台、NumPy、PyTorch、CUDA、GPU、`torch.__config__`、源码 hash 或 cwd。 | 分离 checkpoint/JSON 后不能独立复现或审计环境。 | 在报告内新增 `environment` 和 `source_manifest` 字段：`sys.version`、`platform.platform()`、`numpy.__version__`、`torch.__version__`、`torch.version.cuda`、`torch.cuda.is_available()`、device 名称、`torch.__config__.show()`、cwd、所有直接/间接导入源码 SHA-256。 |
| GPU 叙述与执行行为不一致 | 脚本只在 `_seed` 中调用 `torch.set_num_threads(1)`（`:61-65`），模型和张量没有 `.to("cuda")`；runbook 却要求保存 CUDA/GPU 查询。 | 当前烟雾实际是 CPU 路径；GPU 可用与否不是该命令的执行条件，也没有 GPU 确定性设置。 | 将 runbook 明确标为 CPU-only smoke 并记录 CPU/线程信息，或新增经测试的显式 `--device cpu|cuda`，同时冻结 CUDA wheel、device、确定性设定和比较策略。不得把此 smoke 报告为 GPU 验证。 |
| 测试入口依赖 cwd | 运行清单的 `python -m unittest ...` 与 `test_weather_oracle.py`/`test_rl_algorithms.py` 的顶层导入依赖工作目录。 | 从项目根或自动化 runner 的其他 cwd 调用会失败。 | Runbook 必须先 `Set-Location $ProjectRoot\route_rl_research\20261103\return_makespan\g24_weather_nfz`，并在第一条验证 `Test-Path .\run_full_map_smoke.py`。长期采用安装包/测试 runner，使 cwd 无关。 |
| checkpoint 缺少加载兼容性资料 | `torch.save` 的 payload（`:142-145`）只含 state dict、算法、seed、两个维度。 | 跨 PyTorch release 或与错误源码组合加载时没有架构/版本/manifest 审计信息。 | 加入 schema version、model hidden dimension、package/source hashes、environment manifest，并在 Windows smoke 后以 `map_location="cpu", weights_only=True` 重载 6 个 checkpoint、严格 `load_state_dict` 到对应模型。 |

## 建议的 Windows 复验顺序

以下命令是 Windows 恢复连接后应执行的**建议**，不代表已在 Windows 执行。`$ProjectRoot` 必须指向已封存的完整项目根。

```powershell
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProjectRoot = '<WINDOWS_PATH>'
Set-Location "$ProjectRoot\route_rl_research\20261103\return_makespan\g24_weather_nfz"
@('.\run_full_map_smoke.py', '..\scorer.py', "$ProjectRoot\reproduction\reviewer_package_semfix\lrphsd\problem.py") |
  ForEach-Object { if (-not (Test-Path $_)) { throw "missing required source: $_" } }

# Replace 3.X and the lockfile only after freezing the approved Windows runtime.
py -3.X -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --require-hashes -r requirements-windows.lock
python -c "import sys,platform,numpy,torch,lrphsd.problem,scorer; print(sys.version); print(platform.platform()); print(numpy.__version__); print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(lrphsd.problem.__file__); print(scorer.__file__)" |
  Tee-Object -FilePath windows_environment.txt
& python -m unittest -v test_weather_oracle.py test_weather_pipeline.py test_rl_algorithms.py test_weather_full_map.py 2>&1 |
  Tee-Object -FilePath windows_unittest_stdout_stderr.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$runId = Get-Date -Format 'yyyyMMdd_HHmmss'
$output = "full_map_smoke_windows_$runId"
if (Test-Path $output) { throw "refusing to overwrite $output" }
& python run_full_map_smoke.py --smoke --output-dir $output 2>&1 |
  Tee-Object -FilePath "$output\stdout_stderr.txt"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Get-ChildItem "$output\*.pt" | Measure-Object | Select-Object -ExpandProperty Count
Get-Content "$output\full_map_smoke_report.json" -Raw | ConvertFrom-Json |
  ConvertTo-Json -Depth 20 | Tee-Object -FilePath "$output\report_pretty.json"
```

接受条件应至少为：单元测试 exit 0、6 个 checkpoint 存在、报告为 `weather_full_map_synthetic_smoke_v1`、PPO/A2C 各包含 seeds 103/211/307，且每项 `complete` 为 `true`。在冻结环境/源码 manifest、保留完整 stdout/stderr 和独立重载验证前，这些结果只可标为 Windows synthetic engineering smoke，不构成新机制、训练优越性、作者比较或 Formal 证据。

## 本次读取文件身份

| 文件 | SHA-256 |
|---|---|
| `WINDOWS_RUNBOOK.md` | `765929328e045179d5c1c43e996a93dcfac683106cf749b34085d482404123ae` |
| `REMOTE_EXECUTION_STATUS.md` | `4a7e414b974e88ea38ddf1407b1626339f008d2e5e3f622b272f11761f628a28` |
| `run_full_map_smoke.py` | `ae379f64d07a8aa357805b4502786b4d183e0994ca3d6b9e9332634bf01b0e8f` |
| `weather_full_map.py` | `7074bd020d1b47075ea5b95f61a41b4d1b03508c7e1633bc63c141d43848f21e` |
| `weather_oracle.py` | `e39a7a3ece64443275ef853bbf346571dfd55bf3d360e903d699836fde3908d3` |
| `weather_policy.py` | `6f15e10030b0ab7e4baef6b7c6fe5297dbf120ec606338d7198a1dfe81985826` |
| `weather_replay.py` | `acc6741be557cd9248cb5826d4b0756217b652edb5318b028a3fbf7e5426bdf1` |
| `rl_algorithms.py` | `4d546bb9f69a624398ee2231a5777a525ce41792194e60829a8ebd489a1c6101` |
| `../scorer.py` | `c6e156b2d770cec2f663eada37c2d39bff1583f672bda4116f81493484409135` |
| `reproduction/reviewer_package_semfix/lrphsd/problem.py` | `f03c2f4201cdea977644d84ab0ad704eb47d4c4389b06b2ac86b9d264463b1cc` |

