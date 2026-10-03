# 开发前失败证据

基线 3e13cccf63a75b05eec12e302d557c3cf99dcaac；Windows 根 uv 环境。

运行 `.venv/Scripts/python.exe -m pytest tests/test_wisersone_auth.py -q`，exit 1：收集时缺少 `aima_ugc.adapters.providers.wisersone`。两个目标场景分别要求首次播种后保留刷新态、损坏运行态禁止用 seed 覆盖。

这是未实现能力的失败证据，不是现有产品故障或 Green 验证。
