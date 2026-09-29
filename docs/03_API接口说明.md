# AIMA_UGC API 使用语义与调用指南

本文面向前端开发、接口联调和后端开发，解释 **AIMA HTTP API 的稳定调用语义、领域边界和机器事实入口**。

它不再手工维护完整 Route/字段清单。完整 Method、Path、Request、Response、operationId 和生成 Client 的唯一机器事实是：

- [backend/src/aima_ugc/contracts/http.py](../backend/src/aima_ugc/contracts/http.py)
- [contracts/openapi/openapi.json](../contracts/openapi/openapi.json)
- [frontend/src/generated/api/](../frontend/src/generated/api/)

运行能力、管理、人工复核等领域还会使用各自 Pydantic Contract；精确集合以当前 FastAPI Assembly 与 OpenAPI 为准。

## 1. 先理解两类调用

### 普通查询

~~~text
Vue Feature
→ Generated Client
→ FastAPI Route
→ Query / Application Service
→ PostgreSQL Query Repository
→ Response Model
~~~

页面不直接理解数据库表；Router 不直接拼 SQL。

### 长任务

~~~text
HTTP 请求
→ 短事务冻结用户输入 / 业务父事实
→ 创建持久 Job
→ 返回已受理
→ Worker 认领并执行
→ 更新父事实、进度、结果
→ 前端查询 / 轮询
~~~

采集、数据导入、Canonical Replay、AI Analysis、Excel Export 等耗时能力不能退回一个 HTTP 请求里同步跑完。

长任务的关键语义不是“哪个 URL 名字好看”，而是：

- 创建时冻结哪些输入；
- 谁拥有业务终态；
- Job 如何重试、取消和恢复；
- 前端查询的是业务父事实还是内部 Job；
- 哪些结果已经提交，哪些只是排队。

架构说明见 [docs/blueprint/04_后端任务API与前端.md](blueprint/04_后端任务API与前端.md)。

## 2. Contract 和生成 Client

生成链固定为：

~~~text
Pydantic Request / Response
→ FastAPI OpenAPI
→ contracts/openapi/openapi.json
→ Orval
→ frontend/src/generated/api/
~~~

Generated Client 是生成物，不手工修改。

后端 Contract 变化时，应同步机器生成链和相应 API/Contract/Frontend Evidence；不要在 Markdown 再手抄一套完整字段表，也不要在前端用平行 Type 掩盖 Contract 漂移。

## 3. 统一错误语义

业务错误使用统一 Problem Response 语义，并携带 request_id 便于关联日志。

常见 HTTP 语义：

- 404：目标资源不存在；
- 409：当前资源状态或结果就绪条件冲突；
- 422：请求 Contract 不合法；
- 401：没有有效身份；
- 403：已有身份但没有所需权限；
- 500：未预期内部错误，响应不得暴露 SQL、Secret、内部路径或 traceback。

精确错误结构以 OpenAPI / Pydantic 为准。日志可以记录安全字段路径和错误码，不应把被拒绝的敏感值或完整 Secret 写进日志。

## 4. Health：live 和 ready 不是一回事

live 只回答“API 进程能否响应”。

ready 回答“当前服务是否具备运行所需基础依赖”，包括数据库、ArtifactStore、日志等本地关键边界。

实现入口：

- [backend/src/aima_ugc/bootstrap/api.py](../backend/src/aima_ugc/bootstrap/api.py)
- [backend/src/aima_ugc/platform/health.py](../backend/src/aima_ugc/platform/health.py)

Provider 实时网络、余额或业务任务成功不由 readiness 证明。

## 5. 身份、管理员和 Secret 边界

AIMA 的业务身份是 Provider-neutral Principal。当前角色与认证状态说明见 [docs/product/03_角色权限与产品状态.md](product/03_角色权限与产品状态.md)。

管理员 Provider 配置遵守：

~~~text
写入 API Key
→ Secret Store

数据库
→ 保存非敏感 Runtime 配置 + secret_ref

读取 API / 审计 / 日志
→ 不返回 Secret 明文
~~~

更新 Provider Config 后，新建 Run 使用当前数据库配置；已经创建的 Run/自动重试继续使用创建时冻结的运行事实，避免同一任务中途漂移。

实现入口：

- [backend/src/aima_ugc/contracts/administration.py](../backend/src/aima_ugc/contracts/administration.py)
- [backend/src/aima_ugc/bootstrap/administration_http.py](../backend/src/aima_ugc/bootstrap/administration_http.py)

## 6. 品牌 / 车型目录：目录事实和运行快照分开

管理员维护 Brand、Alias、Vehicle 归属；任务执行时不能每一步重新读取实时目录。

创建导入或采集任务时，会冻结对应 Brand/Vehicle Filter Snapshot。选择全部 active Brand 或指定 Brand，最终都转成可审计的运行快照。

重要语义：

- active Vehicle 必须有合法 Brand 归属；
- Alias 冲突保留为冲突事实，Resolver fail-safe，不猜唯一实体；
- 目录版本变化不会反向改写已创建任务的 Snapshot；
- Excel 与 TikHub 可以复用同一 Brand/Vehicle Resolver，但搜索关键词与品牌过滤不是一件事。

长期边界见 [docs/blueprint/02_采集系统与数据标准化.md](blueprint/02_采集系统与数据标准化.md)。

## 7. Collection：能力由后端投影，前端不维护平台 if/else

Collection API 的核心资源包括：

- 平台/Provider Capability；
- 手工 Run；
- Run/Scope 进度；
- 采集运行中心统一 Read Model。

前端读取后端 Capability 决定排序、时间筛选、评论/二级评论等可用能力，不能维护第二套平台能力表。

当前运行模式的业务差异、Supplement 和评论阶段说明见：

- [docs/blueprint/08_采集策略与平台能力.md](blueprint/08_采集策略与平台能力.md)
- [docs/collection/README.md](collection/README.md)

采集运行中心把不同父资源投影成统一列表，不代表数据库存在一个“万能运行表”。

## 8. Data Import：来源和写入策略是两个维度

当前页面的主导入工作流是 Data Import Campaign。

两类来源：

~~~text
local_upload
server_path
~~~

两类写入策略：

~~~text
standard_observation
historical_fill_only
~~~

来源只决定输入文件怎样安全进入系统；写入策略决定 Content Owner 怎样处理 Current/Version/Metric。二者不能互相推导。

### 本地上传

浏览器先提交冻结文件清单，再逐 Item 上传内容，全部完成后 finalize。重试上传必须仍与被冻结的文件身份一致，不能用同一个 Item 替换成另一份文件。

### 服务器目录

只能枚举管理员批准、只读挂载的根目录内相对路径；拒绝绝对路径、路径逃逸和链接组件。它不是通用服务器文件管理 API。

### Campaign 终态

进度来自 PostgreSQL 持久事实，不由前端猜百分比。取消、失败重试、冲突、补采资格和撤销都围绕同一个 Campaign 业务父事实工作。

具体实现和排障见 [docs/appendix/08_数据入口与统一入库实现.md](appendix/08_数据入口与统一入库实现.md)。

## 9. 兼容 Import / Historical API 为什么还存在

旧 Import Batch 与 Historical Import Contract 仍可能存在于当前 OpenAPI，用于兼容历史调用和数据；它们不等于当前页面需要维持第二套主导入入口。

判断一个 API 是否仍存在、是否标记 deprecated，以 [contracts/openapi/openapi.json](../contracts/openapi/openapi.json) 为准，不以本文的人工列表判断。

长期原则：

~~~text
兼容入口可以继续存在
≠
产品必须继续暴露平行主流程
~~~

## 10. Persistent Canonical Replay

Replay 解决“Canonical 已经存在，但现在的 Brand/Vehicle 目录能够得到新的合法归类”的场景。

HTTP 层负责：

- 冻结目标 Artifact / 全量选择；
- 冻结当前目录快照；
- 建立幂等业务请求与持久 Job；
- 提供查询、取消和撤回入口。

Worker 才负责预检、Replay、去重、Content Owner 收敛和贡献账本。

撤回不根据“现在看起来像谁创建了这条 Content”猜测，而按 Replay 当时原子记录的可逆贡献和当前后续接管状态恢复；后续写入、人工锁和共享来源优先受到保护。

详细实现见 [docs/appendix/08_数据入口与统一入库实现.md](appendix/08_数据入口与统一入库实现.md)。

## 11. Content：列表、详情和评论分页是不同 Read Model

声音广场的 Content 查询读取当前业务视图，AI irrelevant 不物理删除 Content 事实。

详情可以返回审计/展示信息；评论浏览使用独立分页 Read Model，避免把一个详情响应当成无限评论容器。

评论线程必须依赖已持久化的 root / parent identity，而不是让前端根据正文、作者名或当前页位置猜父子关系。

Content / Comment 的精确 Query 参数、Cursor 和字段以 OpenAPI 为准；用户行为见 [docs/product/02_当前产品能力与用户流程.md](product/02_当前产品能力与用户流程.md)。

## 12. 人工 Relevance / Analysis 覆盖不是改写模型历史

人工相关性决定和 Analysis 人工覆盖都绑定当前业务版本/维度，追加自己的审计事实。

模型原始结果不会因为人工纠正被直接删除。撤销人工覆盖后，系统才能回到当前有效 AI/继承语义。

这保证“模型当时给过什么结论”和“当前业务最终采用什么结论”可以同时追溯。

## 13. Analysis Run：Preview / Run / Shard 分层

新版 Analysis 页面语义：

~~~text
Preview
→ 明确目标、当前 Provider/Taxonomy、预计运行边界

Run
→ 冻结目标 Content Version 与运行快照

Planner / Shard Job
→ 后台有界执行

Run Read Model
→ 用户查看一轮任务的历史、进度和结果
~~~

旧 content-analysis request 入口仍可兼容，但不应该被文档描述成新版页面唯一入口。

详细实现见 [docs/appendix/07_AI舆情打标与分析实现.md](appendix/07_AI舆情打标与分析实现.md)。

## 14. Export：创建请求和文件就绪分开

正式 Excel Export 创建时冻结目标 Content Version，后台 Job 生成 Artifact。下载只有在 Artifact 已就绪时成功；结果未就绪不能返回一个空文件冒充成功。

Excel 格式和离线调试见 [docs/appendix/06_Excel统一数据导出与离线调试.md](appendix/06_Excel统一数据导出与离线调试.md)。

Word 报告当前是独立离线 Reporting 能力；是否已经存在正式 HTTP Report 资源只看当前 OpenAPI，不从计划文档猜。

## 15. Keyword Pack 和 Collection Plan 的职责

Keyword Pack 提供 TikHub Discovery 的 Search Terms。

Collection Plan 冻结周期采集所需的 Keyword Pack、Brand Scope、Schedule 等事实；Scheduler 只产生调度事实，真正 Provider 调用由 Worker 执行。

完整 Scheduler 行为见 [docs/appendix/05_Scheduler调度执行与停机恢复.md](appendix/05_Scheduler调度执行与停机恢复.md)。

Search Terms、Brand/Vehicle Filter 和 AI Relevance 是三层不同语义，不要合并成一个“关键词相关性”开关。

## 16. Resource Lifecycle：归档、恢复、删除、撤销不是一个动作

Keyword Pack、Collection Plan、Provider Config、Analysis Scheme 等配置资源需要保留历史引用时，归档优先于物理删除。

永久删除由服务端根据真实引用资格判断，前端不能仅因为列表上“没有使用”就直接 DELETE。

Data Import Campaign 撤销是另一类动作：撤回该来源仍拥有的业务贡献，但保留 Raw、Canonical、审计和共享来源事实。

统一说明见 [docs/appendix/11_业务资源生命周期与数据撤销实现.md](appendix/11_业务资源生命周期与数据撤销实现.md)。

## 17. Cursor 分页

多个列表使用不透明 Cursor，而不是让客户端理解数据库排序键。

客户端只原样回传 next_cursor：

- 不解析；
- 不修改；
- 不跨筛选条件复用；
- 不自己生成。

Cursor 与查询条件、排序和资源身份绑定。精确编码由对应模块与 Contract 持有，不在本文复制。

## 18. 前端如何找到正确 API

当前页面 Route 的机器事实是 [frontend/src/app/routes.ts](../frontend/src/app/routes.ts)。

页面与 API 的映射原则：

~~~text
Page / Store
→ Feature api.ts
→ Generated Client
→ OpenAPI Contract
~~~

当前页面能力和 Feature Owner 见 [frontend/README.md](../frontend/README.md)。后端存在兼容资源，不代表前端需要建立独立页面。

## 19. 修改 API 时检查什么

### 查询字段变化

至少检查：

~~~text
Contract
→ Query Service / Repository
→ Cursor query identity（受影响时）
→ API / Contract Evidence
→ OpenAPI
→ Generated Client
→ Frontend consumer
→ 文档语义
~~~

### 长任务变化

至少检查：

~~~text
业务父事实
→ Job Payload / Registry / Handler
→ Retry / Fence / Progress / Cancel
→ HTTP Contract
→ Worker / Integration Evidence
→ 用户 Read Model
~~~

### Response 变化

先做兼容性判断，再更新 Pydantic / Route / OpenAPI / Generated Client / consumer。不要用前端 any 或手写平行 Type 掩盖不一致。

通用实现与 Review 方法遵守 [AGENTS.md](../AGENTS.md) 指定的 Agent_Skills 治理，本页只给 AIMA 的事实链。

## 20. 联调时从机器事实开始

推荐顺序：

1. [contracts/openapi/openapi.json](../contracts/openapi/openapi.json)
2. 对应 Pydantic Contract
3. 对应 FastAPI Assembly / Application Service
4. [frontend/src/generated/api/](../frontend/src/generated/api/)
5. 对应 API / Contract / Integration / Full-stack test
6. 必要时再构造人工请求

本文是人类语义导航，**不是完整 API Catalog**。新增或删除 Route 后，OpenAPI 已经是精确事实；只有当调用语义、领域边界或读者任务发生变化时才需要同步本文。
