# E下一轮容量检查：中断保留，未通过全规模准入

事前固定9输出流×8192记录，仅重复填充三条新完成关系PPO的原始TRAIN日志作存储工作负载；不运行物理策略/训练、不制造科研样本，不接续旧中断存储探针。原source经既有完整审计绑定SHA。CPU210秒、wall300秒、新bytes900MB上限事前固定。

实际SSH命令返回255，stderr为空；后续现场probe进程不存在、RESULT不存在。不能从SSH255断言远端具体exit/signal。最后持久PROGRESS为7流、57344条逐原字节比较通过、存储394827887bytes、CPU207.251479077秒/wall251.54468391183764秒；第8流部分文件11806858bytes无封口manifest；第9流未执行。所有输出保留、不扩额、不续接重跑。

三原源SHA事后复核均不变，7完整manifest逐SHA取回重开；POST_INTERRUPTION记录实际blob大小/SHA和进程状态。单流样形容量可以观察，9流完整工作负载以及新复杂域/VAL/SELECT/新增metadata/模型/gradient总容量尚无通过证据。此失败如实进入下一科学启动条件；不会以已完成7流替代预定9流。

新预算训练/消融/在线入口25工程测试另已通过，见../20261106_multiobjective_round_E_bootstrap/REPORT.md。原D仍活动，85冻结源事后零变更，原上限保持。

## 首命令、输入与逐字结果

```json
{
  "command": [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    "<LOCAL_HOME>/.ssh/liu2026_repro_ed25519",
    "-p",
    "30635",
    "<REMOTE_ACCOUNT><EXPERIMENT_SERVER><SERVER_DOMAIN>",
    "<SERVER_PATH> -u <SERVER_PATH>"
  ],
  "input": "PLAN.json fixed 9x8192 storage-only workload",
  "stdout": "{\"completed_streams\": 1, \"stored_bytes\": 56461197}\n{\"completed_streams\": 2, \"stored_bytes\": 112761685}\n{\"completed_streams\": 3, \"stored_bytes\": 169183345}\n{\"completed_streams\": 4, \"stored_bytes\": 225644542}\n{\"completed_streams\": 5, \"stored_bytes\": 281945030}\n{\"completed_streams\": 6, \"stored_bytes\": 338366690}\n{\"completed_streams\": 7, \"stored_bytes\": 394827887}\n",
  "stderr": "",
  "exit_status": 255
}
```

## 事后现场（完整）

```json
{
  "time_utc": "2026-11-06T08:14:31.550617+00:00",
  "processes": [],
  "result_present": false,
  "last_progress": {
    "completed_streams": 7,
    "stored_bytes": 394827887,
    "cpu_s": 207.251479077,
    "wall_s": 251.54468391183764
  },
  "files": {
    "storage_only_6.jsonl.gz.manifest.json": {
      "bytes": 590,
      "sha256": "b63efd92129bca4920fc372cab82048f91c2113da3cf57e01d040b4dfb8480b6"
    },
    "PLAN.json": {
      "bytes": 646,
      "sha256": "74b875a2921e0e021428b249ba91d2fde398d219b83345998ae9568c14117ead"
    },
    "storage_only_1.jsonl.gz.manifest.json": {
      "bytes": 590,
      "sha256": "c9695fa02865cffeb8a7cf7ae1990d76b806395d7dd85f993f88e6e4cfbe456a"
    },
    "storage_only_0.jsonl.gz": {
      "bytes": 56461197,
      "sha256": "2ac882fd886f61e1a66514eb26d711e7c69dc6786ed12495ffdcabacd6772e5e"
    },
    "storage_only_2.jsonl.gz": {
      "bytes": 56421660,
      "sha256": "21235274854d74cdee89c30aefa5fe662d023b91a35628dff8543cbe21057aa0"
    },
    "STARTED.json": {
      "bytes": 1127,
      "sha256": "564f38aad174d6e8c8ade61a73b4b5d6a7a867023265e96817f6d80aaa8ce8aa"
    },
    "storage_only_1.jsonl.gz": {
      "bytes": 56300488,
      "sha256": "690b84d7da46bb8ad36acc269fc23bc6f1c97186a1d9116ab85a372ee2dd5f38"
    },
    "PROGRESS.json": {
      "bytes": 105,
      "sha256": "aaee9312965aa9e91e94b10e3355de4ee2a834fc2d1742e1c1d454c669d70970"
    },
    "storage_only_0.jsonl.gz.manifest.json": {
      "bytes": 590,
      "sha256": "fdcb514070e595ab9cd3572d0273d1e0ffe54a3ab673c4c491ff42946ece8638"
    },
    "probe.py": {
      "bytes": 4035,
      "sha256": "c52470eb3b13269e58c62243d18a48a6baf6ed5339827248e7a93a7d6eb7f890"
    },
    "storage_only_6.jsonl.gz": {
      "bytes": 56461197,
      "sha256": "2ac882fd886f61e1a66514eb26d711e7c69dc6786ed12495ffdcabacd6772e5e"
    },
    "storage_only_4.jsonl.gz": {
      "bytes": 56300488,
      "sha256": "690b84d7da46bb8ad36acc269fc23bc6f1c97186a1d9116ab85a372ee2dd5f38"
    },
    "storage_only_5.jsonl.gz.manifest.json": {
      "bytes": 590,
      "sha256": "03bac467b873c425522ed780aa5955ec7f91124d26a2dcf3ae3a42f4f10c5894"
    },
    "storage_only_4.jsonl.gz.manifest.json": {
      "bytes": 590,
      "sha256": "66ae5d97448910c04ce45b28cc30d59e3ef0383a291eb92baa5ac0e7bb1c3984"
    },
    "storage_only_3.jsonl.gz": {
      "bytes": 56461197,
      "sha256": "2ac882fd886f61e1a66514eb26d711e7c69dc6786ed12495ffdcabacd6772e5e"
    },
    "storage_only_3.jsonl.gz.manifest.json": {
      "bytes": 590,
      "sha256": "ae3c651f489c876e4bf66ab3578b1d9bc72b7fd88ed2ee193ace280f1ce53e3c"
    },
    "storage_only_2.jsonl.gz.manifest.json": {
      "bytes": 590,
      "sha256": "f974e22d6f1885a7e29fd523dae17b871573c94cf1acc2e772a2af77b1d1f060"
    },
    "storage_only_5.jsonl.gz": {
      "bytes": 56421660,
      "sha256": "21235274854d74cdee89c30aefa5fe662d023b91a35628dff8543cbe21057aa0"
    },
    "storage_only_7.jsonl.gz": {
      "bytes": 11806858,
      "sha256": "c3e84525d7d02a57f3945b1138a6e186c3701a14f5eb4eb7be2c8855cb72e72f"
    }
  },
  "free_bytes": 5921456128
}
```
