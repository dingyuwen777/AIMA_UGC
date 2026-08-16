# TikHub 五平台主链真实 Endpoint Ledger

本目录来自 GitHub-hosted Runner 的受限真实 Probe，源 Run：`31954514173`。

- Provider Base URL：`https://api.tikhub.io`
- 关键词：`爱玛`
- 真实请求数：22
- 隐藏重试：0
- 所有业务 endpoint：HTTP 200
- 原始真实响应只在 Runner 内存/临时盘存在；提交内容已经严格去标识化。
- 每个平台一个 `*.sanitized.json`，其中按 endpoint 保存实际 Request 与 Response。
- 该目录是人工核查事实源；生产 Mapper 回归仍可继续使用平台目录下更小的结构 Fixture。

任何新 Provider 版本或 endpoint 变更都必须重新执行受限真实 Probe，不得手工猜响应字段。
