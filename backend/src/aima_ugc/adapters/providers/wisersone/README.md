# WisersOne 下载 Provider

此目录负责网站会话、过去 24 小时筛选、一次导出提交、任务轮询和完整 Excel 保存。Provider 不写业务表；系统调度和统一导入由 Ingestion 编排。

`wisersone-auth/wisersone_state.json` 与 `wisersone_runtime.json` 是用户在 Issue #700 批准随代码、wheel、镜像保存的初始状态。仅运行目录两份状态都不存在时播种。刷新状态与提交回执写到 `AIMA_HOST_ROOT/runtime/wisersone-auth`，Compose 将该宿主目录 bind 到 `/run/wisersone-auth`；镜像升级不会覆盖它。损坏或缺少一份文件时明确报错，不能用旧 bundle 静默覆盖。操作采用 OS 跨进程锁和单文件原子替换。

人工入口和命令见 [wisersone_test](../wisersone_test/README.md)。网站生成没有 30 分钟总等待上限；网络/页面单次操作有有限超时。会话过期或网站撤销授权时仍需重新登录并更新完整运行态；这不是永久密码凭据替代品。认证内容不进入日志、Job、数据库或测试证据。

自动计划、输入保留和恢复的唯一流程说明见 [统一数据入口](../../../../../../docs/appendix/08_数据入口与统一入库实现.md)。
