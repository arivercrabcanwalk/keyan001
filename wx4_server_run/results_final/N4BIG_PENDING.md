# N4big 状态（主结果上传时）

- `N4f_M32` / `N4p_M32`，Test-A 天气 7200–7203，400 个任务
- 2026-11-15 19:29:06 UTC 在 A 上启动，38 worker
- 主归档 `results_out_main.tar.xz` 不包含这 400 行
- 完成后会重跑 `analyze_v4.py`、重新打包 `results_out.tar.xz`，并更新本目录

这不是跳过：N4big 是预注册的参考比较，放在主测试之后以缩短主结果等待时间。
