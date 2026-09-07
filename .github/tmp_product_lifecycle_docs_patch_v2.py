from pathlib import Path


def insert_after_once(path: str, anchor: str, addition: str, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    count = text.count(anchor)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one anchor, got {count}')
    if addition.strip() in text:
        return
    target.write_text(text.replace(anchor, anchor + addition, 1), encoding='utf-8')


def replace_between_once(path: str, start: str, end: str, body: str, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    start_count = text.count(start)
    if start_count != 1:
        raise RuntimeError(f'{label}: expected one start anchor, got {start_count}')
    start_pos = text.index(start) + len(start)
    end_pos = text.find(end, start_pos)
    if end_pos < 0:
        raise RuntimeError(f'{label}: end anchor missing')
    target.write_text(text[:start_pos] + body + text[end_pos:], encoding='utf-8')


def append_once(path: str, marker: str, body: str) -> None:
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    if marker in text:
        return
    target.write_text(text.rstrip() + '\n\n' + body.strip() + '\n', encoding='utf-8')


insert_after_once(
    'docs/blueprint/03_数据库与文件存储.md',
    'Provider Secret 不放这里明文保存，数据库只保存 `secret_ref` 等安全引用。',
    '\n\nKeyword Pack 与 Provider Config 现在有独立归档状态。归档不是 `enabled=false` 的别名：归档资源退出普通配置目录和新运行入口；恢复后仍保持停用，历史引用继续保留。是否允许永久删除由引用/历史资格守卫判断，不能根据“当前停用”直接删除。',
    'blueprint03 system lifecycle',
)
insert_after_once(
    'docs/blueprint/03_数据库与文件存储.md',
    '这些表保存**采集执行事实和来源账本**，不是 Content Current 的平行副本。',
    '\n\n`collection_plans` 现在有独立归档状态。归档计划退出 Scheduler 扫描和普通启停/读取入口，恢复后保持停用；计划编辑提升既有 `schedule_version`，已有 Occurrence/Run 继续按当时冻结版本解释。',
    'blueprint03 collection lifecycle',
)
insert_after_once(
    'docs/blueprint/03_数据库与文件存储.md',
    '旧物理名称为避免高风险 Schema 改名而保留，不代表平行业务入口。',
    '\n\nData Import Campaign 撤销另外保存来源 Contribution、Campaign 撤销事实和撤销生成 Version 的追溯。撤销不改写原 Campaign 终态，也不删除输入 Artifact、逐行账本或历史 Version；只有精确可逆证据完整的 Campaign 才能提交撤销。',
    'blueprint03 ingestion revocation',
)
insert_after_once(
    'docs/blueprint/03_数据库与文件存储.md',
    'Content 是外部 UGC 事实的 Owner。',
    '`content_source_contributions` 保存来源对 Current 的精确可逆贡献；查询层会排除只剩已撤销来源支持的 Content。共享 Content 只撤销指定来源贡献，仍有其它有效来源时继续可见；Raw、旧 Version 和来源追溯不会因此被抹掉。\n\n',
    'blueprint03 content visibility',
)
insert_after_once(
    'docs/blueprint/03_数据库与文件存储.md',
    '`analysis_schemes / analysis_scheme_versions` 管理完整配置版本。唯一 active Version 是运行时事实，Git Prompt 只在空库 bootstrap；Run 冻结 Version ID 和编译 Prompt 快照。草稿保存追加 Version，发布/回滚切换完整版本，历史 Version 不删除。',
    '\n\nAnalysis Scheme 现在增加聚合级归档/恢复/条件删除：当前 active Scheme 不能归档；恢复后仍保持非 active；曾发布或进入 Analysis Run 历史的 Scheme/Version 继续保留，只有从未发布、从未使用的纯草稿 Scheme 在归档后才允许永久删除。',
    'blueprint03 analysis lifecycle',
)

replace_between_once(
    'docs/blueprint/04_后端任务API与前端.md',
    '### 3.1 Router\n\n当前主 Router 与最终 API Assembly：\n\n',
    '\n\nRouter 负责：',
    '''- [`backend/src/aima_ugc/bootstrap/api.py`](../../backend/src/aima_ugc/bootstrap/api.py)
- [`backend/src/aima_ugc/bootstrap/analysis_capability_http.py`](../../backend/src/aima_ugc/bootstrap/analysis_capability_http.py)
- [`backend/src/aima_ugc/bootstrap/import_revocation_http.py`](../../backend/src/aima_ugc/bootstrap/import_revocation_http.py)
- [`backend/src/aima_ugc/bootstrap/resource_lifecycle_http.py`](../../backend/src/aima_ugc/bootstrap/resource_lifecycle_http.py)
- [`backend/src/aima_ugc/bootstrap/provider_lifecycle_http.py`](../../backend/src/aima_ugc/bootstrap/provider_lifecycle_http.py)
- [`backend/src/aima_ugc/bootstrap/analysis_scheme_lifecycle_http.py`](../../backend/src/aima_ugc/bootstrap/analysis_scheme_lifecycle_http.py)
- [`backend/src/aima_ugc/entrypoints/api_main.py`](../../backend/src/aima_ugc/entrypoints/api_main.py)''',
    'blueprint04 router assembly',
)
replace_between_once(
    'docs/blueprint/04_后端任务API与前端.md',
    'Service 表达一个业务动作，例如：\n\n```text\n',
    '\n```',
    '''创建一次 Collection Run
列出采集运行中心记录
创建/预检/启动 Data Import Campaign
预览并安全撤销已完成 Data Import Campaign
兼容上传单个 Excel Import Batch
预检并创建 Content Analysis Run
创建 Excel Export
创建/编辑/复制/启停/归档 Collection Plan
维护 Keyword Pack / Provider / Analysis Scheme 生命周期与连接测试''',
    'blueprint04 service examples',
)
insert_after_once(
    'docs/blueprint/04_后端任务API与前端.md',
    '前端不能维护另一套平行 Request/Response Type 来“暂时对齐”。',
    '\n\n产品页面默认层同时遵守“业务语义上浮、工程语义下沉”：用户主要看到文件/来源、业务状态、处理结果、配置名称和可执行动作；Batch/Campaign/Job/Run/UUID、Provider Attempt、Raw Artifact、原始 error/reason code 等继续保留，但只在技术详情或审计追溯层出现。',
    'blueprint04 product projection',
)
insert_after_once(
    'docs/blueprint/04_后端任务API与前端.md',
    '`collection-runtime/runs` 是统一只读投影，不意味着 Data Import Campaign、兼容 Excel Import Batch 和 Collection Run 被合并成一张万能表。当前页面导入主链以 Campaign 为父事实；运行中心直接投影 Campaign 的状态、持久进度和行统计，旧 Import Batch 仅继续承担兼容入口。汇总统计必须按父事实计数，不能再把 Campaign 下的物理 Chunk Batch 重复算作独立导入。',
    '\n\n“取消任务”和“撤销已完成导入”是两个不同动作：取消只终止尚未完成的执行；撤销先计算来源贡献影响，再在资格允许时撤回该 Campaign 的当前业务贡献。撤销不会按 Campaign 粗暴 DELETE Content，也不会改写共享来源仍需要的数据。',
    'blueprint04 cancel vs revoke',
)

insert_after_once(
    'docs/blueprint/08_采集策略与平台能力.md',
    '执行时不再读取一套变化后的全局配置。车型随后改名、废弃或合并不会改写已创建 Run 的冻结语义；历史 Content 车型证据仍保留原标准身份和目录版本。',
    '\n\n### 7.1 配置资源生命周期不改写历史冻结事实\n\nKeyword Pack、Collection Plan 和 Provider Config 都可以退出当前业务目录，但“停用”和“归档”语义不同：停用仍是当前可管理配置，归档则退出新的 Import/Scheduler/Plan/Provider 选择。恢复后保持停用，必须再次显式启用才参与运行。\n\n历史 Run/Campaign 已冻结的 Pack/Plan/Provider 身份和版本不因后续编辑、归档、恢复或重命名漂移。永久删除采用保守资格：只要存在历史计划、运行、导入、Provider Request 等引用，就只允许保留归档记录。',
    'blueprint08 lifecycle freeze',
)

insert_after_once(
    'docs/collection/README.md',
    '手工 Discovery 默认选择 Capability 可支持的 `latest + 1d + all`，并允许逐平台修改；缺少原生时间筛选等能力的平台不会显示或发送对应字段。新建周期 Plan 必须显式完成每个平台的所有受支持维度。已有 Plan 的空配置继续沿用历史 Adapter 默认行为，不做静默迁移。',
    '\n\nKeyword Pack / Collection Plan / Provider Config 现在都有独立归档生命周期。归档资源不会进入新的冻结快照、Scheduler 或 Provider 选择；恢复后保持停用。历史 Run/Occurrence/Provider Request 继续引用原身份和冻结配置，因此有历史引用的资源只允许归档，不能为了目录整洁物理删除。详细实现见 [`docs/appendix/11_业务资源生命周期与数据撤销实现.md`](../appendix/11_业务资源生命周期与数据撤销实现.md)。',
    'collection lifecycle',
)

insert_after_once(
    'backend/src/aima_ugc/modules/ingestion/README.md',
    'AI `relevance = relevant/irrelevant` 属于 Analysis Domain，导入不会自动创建 AI Job。',
    '''

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

原 Campaign、Source/Chunk Artifact、逐行 outcome、Raw、旧 Content Version 和审计继续保留；同一 Campaign 重复撤销幂等。`standard_observation` 与 `historical_fill_only` 都在各自业务写事务中记录 Contribution，因此机制上线后的新导入进入同一可撤销模型。''',
    'ingestion revoke section',
)

append_once(
    'backend/src/aima_ugc/modules/content/README.md',
    '## 18. 导入撤销怎样影响 Content Current 与可见性',
    '''---

## 18. 导入撤销怎样影响 Content Current 与可见性

Data Import Campaign 撤销由 Ingestion 表达用户动作，但实际 Current 重组继续通过 Content Owner 完成。新导入写入时会保存来源对 Current 的精确 Contribution；撤销只回退仍属于该来源、且没有被后续来源覆盖的字段。

查询可见性按有效来源判断：

```text
仍有至少一个未撤销来源
→ Content 继续进入声音广场 / 新 Analysis Target / 新 Export Target

只剩已撤销来源
→ 退出新的业务查询与处理目标
```

这不等于删除历史。Content 身份、Raw Artifact、旧 Version、来源追溯和撤销生成的 Version 都继续保留；共享 Content 不会因为其中一个导入 Campaign 被撤销而误删其它来源贡献。完整边界见 [`docs/appendix/11_业务资源生命周期与数据撤销实现.md`](../../../../../docs/appendix/11_业务资源生命周期与数据撤销实现.md)。''',
)

insert_after_once(
    'backend/src/aima_ugc/modules/analysis/README.md',
    'Python、前端和 Blueprint/Appendix 不维护第二套具体 AI 业务 Taxonomy 列表。',
    '\n\nAnalysis Scheme 聚合支持复制、归档、恢复和条件永久删除，但不改变既有 Version 状态机：当前 active Scheme 不能归档；恢复后仍保持非 active；曾发布或进入 Analysis Run 历史的 Scheme 只允许归档；只有从未发布、从未使用的纯草稿 Scheme 才能在归档后永久删除。管理员页面以结构化发声类型、情感和标签编辑为主路径，Prompt 只在高级设置维护。',
    'analysis scheme lifecycle',
)
