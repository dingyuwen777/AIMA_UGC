from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one anchor, got {count}')
    target.write_text(text.replace(old, new, 1), encoding='utf-8')


# Product：只描述用户当前真正可操作的产品行为；工作台章节保持原样。
replace_once(
    'docs/product/02_当前产品能力与用户流程.md',
    '''- 查看 Content 列表和详情；
- 按文本、平台、内容类型、时间、来源、AI 分类等正式条件筛选；
- 查看当前 Analysis 的 completed / stale / pending 等产品状态；
- 查看 AI 原判和当前有效相关性来源；
- 对当前 Content Version 做人工相关性复核或撤销复核；
- 对明确选择的内容，或数据库当前全部 Content Current，显式创建 Analysis Run；
- 查看活动 Analysis Run 的真实进度并取消；
- 创建正式 Excel Export、查看进度并下载已完成 Artifact。

来源 Batch/Run 等内部标识可以由跨页面深链带入，但普通用户不需要知道 ID 才能使用声音广场；页面不保留“手工输入来源 Batch / Run ID”作为常规筛选方式。''',
    '''- 查看声音列表和详情；详情主层展示平台、作者、内容类型、发布时间、业务来源、内容可用状态、AI 结果和互动数据，内部 Content/Attempt/Artifact/Batch/Run 等身份只在“技术详情”追溯；
- 按文本、平台、车型、AI 相关性和发布时间等高频条件直接筛选；内容类型使用系统真实标准值，标签、AI 状态、发声类型、情感等低频条件集中在“更多筛选”；
- 查看 AI 分析是否已完成、是否需要重新分析，并查看 AI 原判和当前有效人工复核结果；
- 对当前内容版本做人工相关性、发声类型、情感、标签和车型复核；
- 对明确选择的内容，或数据库当前全部可见 Content Current，显式创建 AI 分析任务；
- 查看活动 AI 分析任务的进度并取消；
- 创建 Excel 导出任务、查看进度并下载已完成文件。

来源 Batch/Run 等内部标识可以由跨页面深链带入，但普通用户不需要知道 ID 才能使用声音广场；页面不保留“手工输入来源 Batch / Run ID”作为常规筛选方式，也不把 API endpoint、LLM Runtime、Job/Run 等实现语言放在默认业务层。''',
    'product voice plaza',
)
replace_once(
    'docs/product/02_当前产品能力与用户流程.md',
    '''- 查看 Excel Import、TikHub Collection Run、Data Import Campaign 等运行摘要；
- 查看排队、运行、成功、失败、取消等状态和详情；
- 发起当前后端 Capability 允许的一次性采集；
- 对符合后端资格的已有批次发起补采；
- 通过单一“导入数据”入口选择本地文件/文件夹或管理员批准的服务器目录；
- 创建 Data Import Campaign，完成预检、启动、进度查看、取消、失败重试和冲突查看；
- 成功导入后进入声音广场查看对应内容。

页面只做资格提示和交互收敛，后端仍是最终业务守卫。''',
    '''- 查看数据导入与辅助补采的业务运行摘要、排队/运行/完成/失败/取消状态和处理结果；
- 发起当前后端 Capability 允许的一次性采集，并对符合资格的既有导入来源发起辅助补采；
- 通过单一“导入数据”入口选择本地文件/文件夹或管理员批准的服务器目录；来源选择与“标准导入 / 历史补空”写入策略相互独立，切换来源不会改写用户已选策略；
- 创建 Data Import Campaign，完成预检、启动、进度查看、取消、失败重试和冲突查看；
- 对已完成且具备精确可逆证据的导入，先查看“撤销影响”，再执行可审计的“撤销本次导入”；共享来源仍需要的数据保留，旧导入证据不足时系统明确拒绝自动撤销；
- 失败导入可以从全局任务中心的“处理失败项”直接回到对应 Campaign；
- 成功导入后进入声音广场查看对应内容。

运行中心默认使用文件、平台、业务状态、进度和结果等用户语言；Batch/Campaign/Job/UUID/error code 仅在“技术详情”中追溯。页面只做资格提示和交互收敛，后端仍是最终业务守卫。''',
    'product collection runtime',
)
replace_once(
    'docs/product/02_当前产品能力与用户流程.md',
    '''- 创建、查看和维护 Keyword Pack；
- 添加关键词和管理词包启停；
- 维护系统唯一的全局 Relevance Config；
- 创建、查看和启停周期 Collection Plan；
- 根据 Provider Capability 展示当前平台真正支持的搜索配置；
- 保存计划只修改调度配置，真正执行仍由 Scheduler 在到期时产生运行。''',
    '''- 创建、查看和维护关键词包；支持编辑名称/说明、添加/修改/删除关键词、复制、启停、归档/恢复，并仅在服务端确认从未进入业务历史且无引用时永久删除；
- 维护系统唯一的全局 Relevance Config；已经冻结到历史导入/采集运行的词包版本不因后续维护漂移；
- 创建、查看、编辑、复制、启停、归档/恢复周期采集计划；计划修改提升调度版本，历史运行继续解释其原冻结配置；只有从未执行且无历史引用的归档计划允许永久删除；
- 根据 Provider Capability 展示当前平台真正支持的搜索配置；
- 归档词包/计划退出普通目录和新运行入口，恢复后保持停用；保存计划只修改调度配置，真正执行仍由 Scheduler 在到期时产生运行。''',
    'product collection strategy',
)
replace_once(
    'docs/product/02_当前产品能力与用户流程.md',
    '''管理员配置涉及模型、Provider、业务目录和运行配置时，Secret 内容不得作为普通业务字段回显。当前精确配置项以管理员 Feature、Pydantic Contract 和数据库实现为准，不在产品文档复制字段表。''',
    '''管理员配置涉及模型、Provider、业务目录和运行配置时，Secret 内容不得作为普通业务字段回显。当前 AI/TikHub Provider 支持用户可理解的“测试连接”，基础身份/服务设置与并发、RPS、重试等高级参数分层展示；历史已使用配置只允许归档，未引用归档配置才可能永久删除，恢复后保持停用且非默认。

AI 分析规则以结构化的发声类型、情感和标签编辑为主路径，Prompt 模板放在高级设置；复制只产生新草稿，当前生效规则不能直接归档，曾发布或进入分析历史的规则不能永久删除。从未发布、从未使用的纯草稿规则只有在归档后才允许安全删除。

操作记录默认展示“谁在什么时候对什么做了什么、结果如何”，原始 event/object/request ID 与安全 JSON 只在技术详情查看。当前精确配置项以管理员 Feature、Pydantic Contract 和数据库实现为准，不在产品文档复制字段表。''',
    'product admin config',
)
replace_once(
    'docs/product/02_当前产品能力与用户流程.md',
    '''全局任务中心位于 App Shell，用来聚合现有 Analysis Run、Collection Runtime、Data Export 等只读任务状态。它没有独立 `/jobs` 路由，也不代表后端增加了一个“万能任务”业务资源。

任务中心的产品价值是：用户离开原页面后仍能知道后台工作是否完成，并能回到对应业务上下文继续操作。''',
    '''全局任务中心位于 App Shell，用来聚合现有 AI 分析、采集/导入和数据导出等后台任务状态。它没有独立 `/jobs` 路由，也不代表后端增加了一个“万能任务”业务资源。

任务中心的产品价值是：用户离开原页面后仍能知道后台工作是否完成，并能回到对应业务上下文继续操作。失败的数据导入会提供“处理失败项”入口并直接定位到对应导入任务；普通用户不需要先复制 Campaign/Job ID 再排障。''',
    'product task center',
)

# Blueprint 03：同步数据库职责，不复制列/DDL。
replace_once(
    'docs/blueprint/03_数据库与文件存储.md',
    '''Provider Secret 不放这里明文保存，数据库只保存 `secret_ref` 等安全引用。''',
    '''Provider Secret 不放这里明文保存，数据库只保存 `secret_ref` 等安全引用。

Keyword Pack 与 Provider Config 现在有独立归档状态。归档不是 `enabled=false` 的别名：归档资源退出普通配置目录和新运行入口；恢复后仍保持停用，历史引用继续保留。是否允许永久删除由引用/历史资格守卫判断，不能根据“当前停用”直接删除。''',
    'blueprint03 system lifecycle',
)
replace_once(
    'docs/blueprint/03_数据库与文件存储.md',
    '''collection_candidate_ingestions
```''',
    '''collection_candidate_ingestions
```

`collection_plans` 现在有独立归档状态。归档计划退出 Scheduler 扫描和普通启停/读取入口，恢复后保持停用；计划编辑提升既有 `schedule_version`，已有 Occurrence/Run 继续按当时冻结版本解释。''',
    'blueprint03 collection lifecycle',
)
replace_once(
    'docs/blueprint/03_数据库与文件存储.md',
    '''processing_import_batch_item_conflicts
```''',
    '''processing_import_batch_item_conflicts
historical_import_campaign_revocations
historical_import_revocation_content_versions
```''',
    'blueprint03 ingestion table list',
)
replace_once(
    'docs/blueprint/03_数据库与文件存储.md',
    '''旧物理名称为避免高风险 Schema 改名而保留，不代表平行业务入口。''',
    '''旧物理名称为避免高风险 Schema 改名而保留，不代表平行业务入口。

Data Import Campaign 撤销是独立、可审计的业务事实，不改写原 Campaign 终态，也不删除输入 Artifact、逐行账本或历史 Version。只有精确可逆证据完整的 Campaign 才能提交撤销；撤销生成的新 Content Version 与 Campaign 单独建立追溯关系。''',
    'blueprint03 ingestion revocation',
)
replace_once(
    'docs/blueprint/03_数据库与文件存储.md',
    '''content_versions
content_metric_observations''',
    '''content_versions
content_source_contributions
content_metric_observations''',
    'blueprint03 content contribution table',
)
replace_once(
    'docs/blueprint/03_数据库与文件存储.md',
    '''Content 是外部 UGC 事实的 Owner。''',
    '''Content 是外部 UGC 事实的 Owner。`content_source_contributions` 保存来源对 Current 的精确可逆贡献；查询层会排除只剩已撤销来源支持的 Content。共享 Content 只撤销指定来源贡献，仍有其它有效来源时继续可见；Raw、旧 Version 和来源追溯不会因此被抹掉。''',
    'blueprint03 content visibility',
)
replace_once(
    'docs/blueprint/03_数据库与文件存储.md',
    '''`analysis_schemes / analysis_scheme_versions` 管理完整配置版本。唯一 active Version 是运行时事实，Git Prompt 只在空库 bootstrap；Run 冻结 Version ID 和编译 Prompt 快照。草稿保存追加 Version，发布/回滚切换完整版本，历史 Version 不删除。''',
    '''`analysis_schemes / analysis_scheme_versions` 管理完整配置版本。唯一 active Version 是运行时事实，Git Prompt 只在空库 bootstrap；Run 冻结 Version ID 和编译 Prompt 快照。草稿保存追加 Version，发布/回滚切换完整版本。曾发布或进入 Analysis Run 历史的 Scheme/Version 继续保留；只有从未发布、从未使用的纯草稿 Scheme 在归档后才允许永久删除。''',
    'blueprint03 analysis lifecycle',
)

# Blueprint 04：同步 API/服务装配与产品层语义。
replace_once(
    'docs/blueprint/04_后端任务API与前端.md',
    '''- [`backend/src/aima_ugc/bootstrap/analysis_capability_http.py`](../../backend/src/aima_ugc/bootstrap/analysis_capability_http.py)
- [`backend/src/aima_ugc/entrypoints/api_main.py`](../../backend/src/aima_ugc/entrypoints/api_main.py)''',
    '''- [`backend/src/aima_ugc/bootstrap/analysis_capability_http.py`](../../backend/src/aima_ugc/bootstrap/analysis_capability_http.py)
- [`backend/src/aima_ugc/bootstrap/import_revocation_http.py`](../../backend/src/aima_ugc/bootstrap/import_revocation_http.py)
- [`backend/src/aima_ugc/bootstrap/resource_lifecycle_http.py`](../../backend/src/aima_ugc/bootstrap/resource_lifecycle_http.py)
- [`backend/src/aima_ugc/bootstrap/provider_lifecycle_http.py`](../../backend/src/aima_ugc/bootstrap/provider_lifecycle_http.py)
- [`backend/src/aima_ugc/bootstrap/analysis_scheme_lifecycle_http.py`](../../backend/src/aima_ugc/bootstrap/analysis_scheme_lifecycle_http.py)
- [`backend/src/aima_ugc/entrypoints/api_main.py`](../../backend/src/aima_ugc/entrypoints/api_main.py)''',
    'blueprint04 http assembly links',
)
replace_once(
    'docs/blueprint/04_后端任务API与前端.md',
    '''创建/预检/启动 Data Import Campaign
兼容上传单个 Excel Import Batch
预检并创建 Content Analysis Run
创建 Excel Export
创建/启停 Collection Plan''',
    '''创建/预检/启动 Data Import Campaign
预览并安全撤销已完成 Data Import Campaign
兼容上传单个 Excel Import Batch
预检并创建 Content Analysis Run
创建 Excel Export
创建/编辑/复制/启停/归档 Collection Plan
维护 Keyword Pack / Provider / Analysis Scheme 生命周期与连接测试''',
    'blueprint04 service examples',
)
replace_once(
    'docs/blueprint/04_后端任务API与前端.md',
    '''`collection-runtime/runs` 是统一只读投影，不意味着 Data Import Campaign、兼容 Excel Import Batch 和 Collection Run 被合并成一张万能表。当前页面导入主链以 Campaign 为父事实；运行中心直接投影 Campaign 的状态、持久进度和行统计，旧 Import Batch 仅继续承担兼容入口。汇总统计必须按父事实计数，不能再把 Campaign 下的物理 Chunk Batch 重复算作独立导入。''',
    '''`collection-runtime/runs` 是统一只读投影，不意味着 Data Import Campaign、兼容 Excel Import Batch 和 Collection Run 被合并成一张万能表。当前页面导入主链以 Campaign 为父事实；运行中心直接投影 Campaign 的状态、持久进度和行统计，旧 Import Batch 仅继续承担兼容入口。汇总统计必须按父事实计数，不能再把 Campaign 下的物理 Chunk Batch 重复算作独立导入。

“取消任务”和“撤销已完成导入”是两个不同动作：取消只终止尚未完成的执行；撤销先计算来源贡献影响，再在资格允许时撤回该 Campaign 的当前业务贡献。撤销不会按 Campaign 粗暴 DELETE Content，也不会改写共享来源仍需要的数据。''',
    'blueprint04 cancel vs revoke',
)
replace_once(
    'docs/blueprint/04_后端任务API与前端.md',
    '''前端不能维护另一套平行 Request/Response Type 来“暂时对齐”。''',
    '''前端不能维护另一套平行 Request/Response Type 来“暂时对齐”。

产品页面默认层同时遵守“业务语义上浮、工程语义下沉”：用户主要看到文件/来源、业务状态、处理结果、配置名称和可执行动作；Batch/Campaign/Job/Run/UUID、Provider Attempt、Raw Artifact、原始 error/reason code 等继续保留，但只在技术详情或审计追溯层出现。''',
    'blueprint04 product projection',
)

# Blueprint 08 / Collection：历史冻结与归档生命周期一致。
replace_once(
    'docs/blueprint/08_采集策略与平台能力.md',
    '''执行时不再读取一套变化后的全局配置。车型随后改名、废弃或合并不会改写已创建 Run 的冻结语义；历史 Content 车型证据仍保留原标准身份和目录版本。

Search Observation 先判断 Rule Relevance。''',
    '''执行时不再读取一套变化后的全局配置。车型随后改名、废弃或合并不会改写已创建 Run 的冻结语义；历史 Content 车型证据仍保留原标准身份和目录版本。

### 7.1 配置资源生命周期不改写历史冻结事实

Keyword Pack、Collection Plan 和 Provider Config 都可以退出当前业务目录，但“停用”和“归档”语义不同：停用仍是当前可管理配置，归档则退出新的 Import/Scheduler/Plan/Provider 选择。恢复后保持停用，必须再次显式启用才参与运行。

历史 Run/Campaign 已冻结的 Pack/Plan/Provider 身份和版本不因后续编辑、归档、恢复或重命名漂移。永久删除采用保守资格：只要存在历史计划、运行、导入、Provider Request 等引用，就只允许保留归档记录。

Search Observation 先判断 Rule Relevance。''',
    'blueprint08 lifecycle freeze',
)
replace_once(
    'docs/collection/README.md',
    '''手工 Discovery 默认选择 Capability 可支持的 `latest + 1d + all`，并允许逐平台修改；缺少原生时间筛选等能力的平台不会显示或发送对应字段。新建周期 Plan 必须显式完成每个平台的所有受支持维度。已有 Plan 的空配置继续沿用历史 Adapter 默认行为，不做静默迁移。''',
    '''手工 Discovery 默认选择 Capability 可支持的 `latest + 1d + all`，并允许逐平台修改；缺少原生时间筛选等能力的平台不会显示或发送对应字段。新建周期 Plan 必须显式完成每个平台的所有受支持维度。已有 Plan 的空配置继续沿用历史 Adapter 默认行为，不做静默迁移。

Keyword Pack / Collection Plan / Provider Config 现在都有独立归档生命周期。归档资源不会进入新的冻结快照、Scheduler 或 Provider 选择；恢复后保持停用。历史 Run/Occurrence/Provider Request 继续引用原身份和冻结配置，因此有历史引用的资源只允许归档，不能为了目录整洁物理删除。详细实现见 [`docs/appendix/11_业务资源生命周期与数据撤销实现.md`](../appendix/11_业务资源生命周期与数据撤销实现.md)。''',
    'collection lifecycle',
)

# 模块 README：同步 Owner 边界。
replace_once(
    'backend/src/aima_ugc/modules/ingestion/README.md',
    '''- [`docs/appendix/08_数据入口与统一入库实现.md`](../../../../../docs/appendix/08_数据入口与统一入库实现.md)
- [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](../../../../../docs/roadmap/03_4000万历史数据迁移实施方案.md)''',
    '''- [`docs/appendix/08_数据入口与统一入库实现.md`](../../../../../docs/appendix/08_数据入口与统一入库实现.md)
- [`docs/appendix/11_业务资源生命周期与数据撤销实现.md`](../../../../../docs/appendix/11_业务资源生命周期与数据撤销实现.md)
- [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](../../../../../docs/roadmap/03_4000万历史数据迁移实施方案.md)''',
    'ingestion doc links',
)
replace_once(
    'backend/src/aima_ugc/modules/ingestion/README.md',
    '''processing_import_batch_item_conflicts
```

精确定义：''',
    '''processing_import_batch_item_conflicts
historical_import_campaign_revocations
historical_import_revocation_content_versions
```

`content_source_contributions` 属于 Content 来源贡献事实，由 Content Owner 负责，不因为撤销能力放到 Ingestion 里重复建 Current/Version 规则。

精确定义：''',
    'ingestion revocation facts',
)
replace_once(
    'backend/src/aima_ugc/modules/ingestion/README.md',
    '''AI `relevance = relevant/irrelevant` 属于 Analysis Domain，导入不会自动创建 AI Job。

---

## 9. 兼容单文件 Import：`/api/v1/import-batches`''',
    '''AI `relevance = relevant/irrelevant` 属于 Analysis Domain，导入不会自动创建 AI Job。

### 8.1 已完成 Campaign 怎样安全撤销

撤销不是取消 Job，也不是按 Campaign 删除 `contents`：

```text
先预览影响
→ 检查该 Campaign 对每个 Content 是否有精确可逆 Contribution
→ 证据不足：fail closed，不允许自动撤销
→ 证据完整：提交 Campaign 撤销事实
→ Content Owner 回退仍属于该来源且未被后续来源覆盖的字段
→ 只有该 Campaign 支撑的 Content 退出当前业务可见视图
→ 仍有其它有效来源的共享 Content 保留
→ 追加可审计的撤销 Version 与追溯
```

原 Campaign、Source/Chunk Artifact、逐行 outcome、Raw、旧 Content Version 和审计继续保留；同一 Campaign 重复撤销幂等。`standard_observation` 与 `historical_fill_only` 都在各自业务写事务中记录 Contribution，因此新导入从机制上线后进入同一可撤销模型。

---

## 9. 兼容单文件 Import：`/api/v1/import-batches`''',
    'ingestion revoke section',
)
replace_once(
    'backend/src/aima_ugc/modules/content/README.md',
    '''- [`docs/appendix/08_数据入口与统一入库实现.md`](../../../../../docs/appendix/08_数据入口与统一入库实现.md)
- [`docs/01_代码结构与修改导航.md`](../../../../../docs/01_代码结构与修改导航.md)''',
    '''- [`docs/appendix/08_数据入口与统一入库实现.md`](../../../../../docs/appendix/08_数据入口与统一入库实现.md)
- [`docs/appendix/11_业务资源生命周期与数据撤销实现.md`](../../../../../docs/appendix/11_业务资源生命周期与数据撤销实现.md)
- [`docs/01_代码结构与修改导航.md`](../../../../../docs/01_代码结构与修改导航.md)''',
    'content doc links',
)
content_path = Path('backend/src/aima_ugc/modules/content/README.md')
content_text = content_path.read_text(encoding='utf-8')
content_tail = '''\n\n---\n\n## 18. 导入撤销怎样影响 Content Current 与可见性\n\nData Import Campaign 撤销由 Ingestion 表达用户动作，但实际 Current 重组继续通过 Content Owner 完成。新导入写入时会保存来源对 Current 的精确 Contribution；撤销只回退仍属于该来源、且没有被后续来源覆盖的字段。\n\n查询可见性按有效来源判断：\n\n```text\n仍有至少一个未撤销来源\n→ Content 继续进入声音广场 / 新 Analysis Target / 新 Export Target\n\n只剩已撤销来源\n→ 退出新的业务查询与处理目标\n```\n\n这不等于删除历史。Content 身份、Raw Artifact、旧 Version、来源追溯和撤销生成的 Version 都继续保留；共享 Content 不会因为其中一个导入 Campaign 被撤销而误删其它来源贡献。完整边界见 [`docs/appendix/11_业务资源生命周期与数据撤销实现.md`](../../../../../docs/appendix/11_业务资源生命周期与数据撤销实现.md)。\n'''
if '## 18. 导入撤销怎样影响 Content Current 与可见性' not in content_text:
    content_path.write_text(content_text.rstrip() + content_tail, encoding='utf-8')

replace_once(
    'backend/src/aima_ugc/modules/analysis/README.md',
    '''Python、前端和 Blueprint/Appendix 不维护第二套具体 AI 业务 Taxonomy 列表。

修改情感、发声类型、一级/二级标签、判断边界或学习示例时：''',
    '''Python、前端和 Blueprint/Appendix 不维护第二套具体 AI 业务 Taxonomy 列表。

Analysis Scheme 聚合现在支持复制、归档、恢复和条件永久删除，但不改变既有 Version 状态机：当前 active Scheme 不能归档；恢复后仍保持非 active；曾发布或进入 Analysis Run 历史的 Scheme 只允许归档；只有从未发布、从未使用的纯草稿 Scheme 才能在归档后永久删除。管理员页面以结构化发声类型、情感和标签编辑为主路径，Prompt 只在高级设置维护。

修改情感、发声类型、一级/二级标签、判断边界或学习示例时：''',
    'analysis scheme lifecycle',
)

# Appendix 11：把机器事实入口改为可导航链接，并校准当前交付状态描述。
appendix_path = Path('docs/appendix/11_业务资源生命周期与数据撤销实现.md')
appendix = appendix_path.read_text(encoding='utf-8')
link_map = {
    '`backend/src/aima_ugc/adapters/persistence/postgres/keyword_lifecycle.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/keyword_lifecycle.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/keyword_lifecycle.py)',
    '`backend/src/aima_ugc/adapters/persistence/postgres/keywords.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/keywords.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/keywords.py)',
    '`backend/src/aima_ugc/adapters/persistence/postgres/scheduled_keywords.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/scheduled_keywords.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/scheduled_keywords.py)',
    '`backend/src/aima_ugc/adapters/persistence/postgres/collection_plan_lifecycle.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/collection_plan_lifecycle.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/collection_plan_lifecycle.py)',
    '`backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py)',
    '`backend/src/aima_ugc/adapters/persistence/postgres/provider_lifecycle.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/provider_lifecycle.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/provider_lifecycle.py)',
    '`backend/src/aima_ugc/adapters/persistence/postgres/system.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/system.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/system.py)',
    '`backend/src/aima_ugc/bootstrap/runtime_config.py`': '[`backend/src/aima_ugc/bootstrap/runtime_config.py`](../../backend/src/aima_ugc/bootstrap/runtime_config.py)',
    '`backend/src/aima_ugc/adapters/providers/connectivity.py`': '[`backend/src/aima_ugc/adapters/providers/connectivity.py`](../../backend/src/aima_ugc/adapters/providers/connectivity.py)',
    '`backend/src/aima_ugc/bootstrap/provider_lifecycle_http.py`': '[`backend/src/aima_ugc/bootstrap/provider_lifecycle_http.py`](../../backend/src/aima_ugc/bootstrap/provider_lifecycle_http.py)',
    '`backend/src/aima_ugc/adapters/persistence/postgres/analysis_schemes.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/analysis_schemes.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/analysis_schemes.py)',
    '`backend/src/aima_ugc/adapters/persistence/postgres/analysis_scheme_lifecycle.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/analysis_scheme_lifecycle.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/analysis_scheme_lifecycle.py)',
    '`backend/src/aima_ugc/adapters/persistence/postgres/content_contributions.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/content_contributions.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/content_contributions.py)',
    '`backend/src/aima_ugc/adapters/persistence/postgres/content_lifecycle.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/content_lifecycle.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/content_lifecycle.py)',
    '`backend/src/aima_ugc/adapters/persistence/postgres/historical_revocation.py`': '[`backend/src/aima_ugc/adapters/persistence/postgres/historical_revocation.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/historical_revocation.py)',
    '`backend/src/aima_ugc/modules/ingestion/revocation.py`': '[`backend/src/aima_ugc/modules/ingestion/revocation.py`](../../backend/src/aima_ugc/modules/ingestion/revocation.py)',
    '`backend/src/aima_ugc/bootstrap/import_revocation_http.py`': '[`backend/src/aima_ugc/bootstrap/import_revocation_http.py`](../../backend/src/aima_ugc/bootstrap/import_revocation_http.py)',
}
for old, new in link_map.items():
    if old not in appendix:
        raise RuntimeError(f'appendix link anchor missing: {old}')
    appendix = appendix.replace(old, new)
appendix = appendix.replace(
    '- 上线前必须完成 OpenAPI/Orval 生成、Migration/PostgreSQL 集成和前端验收；',
    '- 合并/上线前仍必须在最新相关 HEAD 上完成 Contract 生成一致性、Migration/PostgreSQL 集成和前端/用户工作流验收；',
)
appendix_path.write_text(appendix, encoding='utf-8')
