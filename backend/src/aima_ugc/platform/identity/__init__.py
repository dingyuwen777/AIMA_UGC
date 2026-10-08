"""平台级身份标识：多企业 Connector 的配置结构与查找。

为什么在 `platform/` 而不是 `modules/`：Connector 是**由环境变量构造的配置结构**，
与 `platform/config/settings.py` 同源；而 `platform/` 是更底层的一层
（`modules/` 依赖 `platform/`，反向依赖会形成循环导入）。
"""
