# Strict Full-Map Synthetic Smoke Results

## Scope

This is an engineering smoke on the hand-written five-target fixture only. It
is not a Liu author-map run, a registered map, a formal comparison, a quality
experiment, or a claim about PPO/A2C effectiveness. `static-route reference`
below means the fixture's fixed route replayed under the common deterministic
weather/NFZ scenario.

Every final result was independently replayed and required both the parent
LRPHSD contract `C_original <= C_reference + 1e-7` and the weather-domain
contract `C_weather <= C_weather_reference + 1e-7`.

## Command And Artifacts

```text
python run_full_map_smoke.py --smoke --output-dir full_map_smoke_20261104_strict_v7
{"report": "<LOCAL_PATH>", "weather_cost_cap": 77.63251698355198}
exit 0
```

The report records the Python/platform/NumPy/PyTorch/CUDA receipt, the fixed
observation schema (`global_dim=1118`, `candidate_dim=19`, 20 slots/128 targets), and SHA-256
source manifest. Each checkpoint is bound to the JSON by SHA-256 and byte
count. All six checkpoints were reloaded with `weights_only=True`, a strict
state-dict load, and an identical-logit/value inference round trip during the
run.

## Results

| Method | Seed | Final complete | `M_return` min | Weather cost | Original cost | Training dead-end / 32 |
|---|---:|---:|---:|---:|---:|---:|
| Static-route reference | - | yes | 4.769978 | 77.632517 | 77.713964 | n/a |
| Greedy physical rule | - | yes | 7.114615 | 76.969880 | 76.768023 | n/a |
| PPO | 103 | yes | 6.682738 | 76.753941 | 76.657737 | 19 |
| PPO | 211 | yes | 6.682738 | 76.753941 | 76.657737 | 19 |
| PPO | 307 | yes | 6.727936 | 76.776540 | 76.768023 | 17 |
| A2C | 103 | yes | 6.682738 | 76.753941 | 76.657737 | 24 |
| A2C | 211 | yes | 6.409009 | 76.617076 | 76.657737 | 22 |
| A2C | 307 | yes | 6.727936 | 76.776540 | 76.768023 | 26 |

All listed learning outputs are slower than the fixture's static-route
reference on `M_return`; their per-seed training failures remain in the JSON
denominator. This is a negative interface observation, not a statistical or
research conclusion. The report JSON is the authoritative receipt for each
candidate's independently recomputed original and weather costs.

## Local Runtime

- Python `3.13.12`, NumPy `2.5.2`, PyTorch `2.12.1`, CUDA unavailable.
- Elapsed wall time: `35.32046524994075` seconds.
- Windows was not reachable during this run; no value in this file is a Windows
  result.
