# WisersOne 人工入口

从仓库根使用唯一 uv 环境，复用正式 Provider 下载；不写系统数据库。

```powershell
uv run python -m aima_ugc.adapters.providers.wisersone_test.test --output-dir E:/downloads/wisersone
```

也可以在本目录运行 `uv run --project E:/work/03_Aima/code/AIMA_UGC python test.py --output-dir E:/downloads/wisersone`。Linux 使用同一模块命令和 Linux 输出路径，无需 UI。默认 headless；`--headed` 仅供有桌面的机器观察。

默认认证运行态为 `AIMA_HOST_ROOT/runtime/wisersone-auth`，源码没有设置 AIMA_HOST_ROOT 时使用仓库 `.runtime/compose`。可用 `--auth-dir` 明确指定现有运行态目录。它包含两份 JSON 和临时替换/非敏感导出回执。运行中不要修改状态文件。人工输出目录由调用者管理，不参加系统七天清理。

系统定时下载请在采集策略中新建 WisersOne 计划，配置计划名称、执行频率、品牌并启用；人工下载不会自动创建该计划。
