"""一次性同步 Stage 3A 已验证事实到长期文档。"""

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: expected exactly one match for {old!r}, got {text.count(old)}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_section(path: str, start: str, end: str, replacement: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError(f"{path}: section markers are not unique: {start!r} / {end!r}")
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    file.write_text(before + replacement + end + after, encoding="utf-8")


def main() -> None:
    replace_once(
        "README.md",
        "**Stage 1 工程基线与 Stage 2 Platform 基础已经建立。** 当前仓库已经具备可安装 Python package、FastAPI/Vue 最小工程、固定 OpenAPI 与生成 TypeScript Client、本地前后端联调、Windows x64 开发环境引导，以及业务无关的 Config、Secret、统一日志、PostgreSQL 连接、`/health/ready`、ArtifactService/ArtifactStore、Local ArtifactStore 和 API/Worker/Scheduler/Migration 最小 bootstrap。\n\n仍未进入业务功能批量开发阶段。Stage 0 的页面/角色、五平台能力矩阵、真实 Fixture、隐私/保留、容量/SLO/RPO/RTO 和 Scheduler misfire 等业务事实继续约束后续实现；下一项正式工程阶段是 Stage 3 Contract / Database / System/Auth。",
        "**Stage 1 工程基线、Stage 2 Platform 基础和 Stage 3A 数据库基础已经建立。** 当前仓库已经具备可安装 Python package、FastAPI/Vue 最小工程、固定 OpenAPI 与生成 TypeScript Client、本地前后端联调、Windows x64 开发环境引导，以及业务无关的 Config、Secret、统一日志、PostgreSQL 连接、`/health/ready`、ArtifactService/ArtifactStore、Local ArtifactStore、Alembic 首条 Revision、Artifact PostgreSQL 元数据 Repository、System Settings 和 Provider 中立 Audit 基础。\n\n仍未进入业务功能批量开发阶段。Stage 0 的页面/角色、五平台能力矩阵、真实 Fixture、隐私/保留、容量/SLO/RPO/RTO 和 Scheduler misfire 等业务事实继续约束后续实现；下一项正式工程工作是 Stage 3B Canonical Contract。",
    )
    replace_once(
        "README.md",
        "- `ArtifactService`：负责 ID、元数据 Port 以及 `pending → stored → linked`；PostgreSQL `artifacts` Repository/Table 留到 Stage 3；",
        "- `ArtifactService`：负责 ID、元数据 Port 以及 `pending → stored → linked`；Stage 3A 已用 PostgreSQL `artifacts` Table/Repository 实现正式元数据持久化；",
    )
    replace_once(
        "README.md",
        "Stage 2 CI 使用隔离 PostgreSQL `18.4` 验证真实连接和 readiness；这只是开发/CI 基线，不等于生产镜像 variant 或 Release digest 已批准。",
        "Stage 2 CI 使用隔离 PostgreSQL `18.4` 验证真实连接和 readiness。Stage 3A 另有独立 PostgreSQL 18.4 Job 验证 `upgrade head → alembic check → Repository 集成 → downgrade base → upgrade head → alembic check`。这些仍只是开发/CI 基线，不等于生产镜像 variant 或 Release digest 已批准。\n\n### Stage 3A：数据库与基础持久化\n\n- 根目录 `alembic.ini` + `migrations/` 是 Schema 演进入口，API/Worker/Scheduler 不自动迁移；\n- 首条 Revision `20260813_0001` 建立 `artifacts`、`system_settings`、`audit_events`；\n- `aima_ugc.database_schema` 注册当前应用 Table，`Table.info['owner']` 是表写 Owner 机器事实；\n- `artifacts` Owner=`platform`，`system_settings`/`audit_events` Owner=`system`；\n- PostgreSQL Artifact Repository 使用条件更新推进 `pending → stored → linked/error`，非法状态转换关闭失败；\n- System Settings 只保存非敏感 JSON 设置；Audit actor 使用 `system/principal` Provider 中立语义；\n- 当前仍不实现本地登录、Session、飞书/OIDC、具体 Role/Permission Schema、API 幂等 actor 表或自动 Retention 删除。",
    )
    replace_once(
        "README.md",
        "→ 阶段 3：Canonical Contract、核心数据库 Schema/Alembic、System/Audit + 第三方身份扩展边界（不实现登录）",
        "阶段 3A：数据库/Alembic/Artifact Metadata/System/Audit 基础已完成\n→ 阶段 3B：Canonical Pydantic / JSON Schema / 固定示例",
    )

    replace_once(
        "docs/环境运行与部署.md",
        "- **Stage 2 Platform 本地配置、PostgreSQL 连接与 `/health/ready`：Go**；",
        "- **Stage 2 Platform 本地配置、PostgreSQL 连接与 `/health/ready`：Go**；\n- **Stage 3A Alembic Migration 与基础 Repository 开发：Go**；",
    )
    replace_once(
        "docs/环境运行与部署.md",
        "生产 No-Go 的原因是业务 Schema/Alembic、认证授权、Job Runtime、正式 Scheduler、Docker Compose 和生产 Release 等后续能力尚未完整落地和验收。Stage 2 的 Config、Secret、日志、数据库连接、readiness 与 Local Artifact 基础已经可用于开发和 CI，但不等于生产部署已完成。",
        "生产 No-Go 的原因是 Canonical/其余业务 Schema、认证授权、Job Runtime、正式 Scheduler、Docker Compose 和生产 Release 等后续能力尚未完整落地和验收。Stage 3A 已建立 Alembic 和三张基础表，但这只证明数据库基础可开发、可迁移，不等于生产 Schema 或部署已完成。",
    )
    replace_once(
        "docs/环境运行与部署.md",
        "Platform 本地运行目录和 Secret 准备完成后，再按第 5 节启动 API；如果 PostgreSQL 尚未准备好，`/health/live` 仍可用于确认进程已启动，而 `/health/ready` 应保持 503。",
        "Platform 本地运行目录和 Secret 准备完成后，再按第 5 节启动 API；如果 PostgreSQL 尚未准备好，`/health/live` 仍可用于确认进程已启动，而 `/health/ready` 应保持 503。\n\n### 4.4 Stage 3A 本地 Migration\n\nMigration 与 API 启动严格分离。准备好同一组 `AIMA_DB_*` 和 `<AIMA_SECRET_DIR>/postgres_password` 后，从仓库根执行：\n\n```bash\nuv run alembic current\nuv run alembic upgrade head\nuv run alembic check\n```\n\n开发/CI 可验证回滚：\n\n```bash\nuv run alembic downgrade base\nuv run alembic upgrade head\nuv run alembic check\n```\n\n`downgrade base` 会删除 Stage 3A 当前三张应用表，只用于空库/隔离开发数据库和 CI 验证；未来有真实数据的生产回滚必须按 Release/备份方案执行，不能机械 downgrade。API/Worker/Scheduler 启动不会自动执行这些命令。",
    )
    replace_once(
        "docs/环境运行与部署.md",
        "- PostgreSQL 业务 Schema、Artifact 元数据 Repository/Table 与 Alembic Revision；\n- Session/RBAC、Job Runtime 和正式 Scheduler；",
        "- Canonical 与其余业务 Schema/Migration；\n- 第三方认证/授权、Job Runtime 和正式 Scheduler；",
    )

    replace_section(
        "docs/blueprint/03-数据库与文件存储.md",
        "### 5.18 `artifacts`\n",
        "## 6. `jsonb` 使用边界",
        """### 5.18 `artifacts`\n\nStage 3A 已由 `20260813_0001` Revision 建立，机器事实以 `platform/storage/tables.py`、Migration 和测试为准：\n\n```text\nid                  uuid primary key\nkind                text not null\nstorage_backend     text not null\nstorage_key         text not null\ncontent_type        text not null\nencoding            text\nsha256              text\nbyte_size           bigint\nretention_class     text not null\nstorage_status      text not null\ncreated_at          timestamptz not null\nstored_at           timestamptz\nlinked_at           timestamptz\nexpires_at          timestamptz\ndeleted_at          timestamptz\n```\n\n唯一 `(storage_backend, storage_key)`；状态只允许 `pending/stored/linked/delete_pending/deleted/error`，并有状态字段一致性 CHECK。Stage 3A PostgreSQL Repository 正式实现 Stage 2 的 `ArtifactMetadataPort`，使用 `id + 当前状态` 条件更新推进 `pending → stored → linked` 或 `pending → error`；并发或非法转换更新不到行时关闭失败，不静默覆盖状态。\n\n`retention_class` 只是未来保留策略的分类入口，`expires_at` 当前可空。具体 Raw/报告/审计保留期限尚未批准，本阶段不自动填写统一到期日，也不实现 Artifact 删除 Job。\n\n### 5.19 `system_settings` 与 `audit_events`\n\nStage 3A 当前 System 持久化只建立两个 Provider 中立共享表：\n\n```text\nsystem_settings\n  key                 text primary key\n  value               jsonb not null\n  version             integer not null default 1\n  created_at          timestamptz not null\n  updated_at          timestamptz not null\n\naudit_events\n  id                  uuid primary key\n  actor_kind          text not null  # system | principal\n  actor_ref           text\n  event_type          text not null\n  object_type         text\n  object_id           text\n  request_id          text\n  safe_detail         jsonb not null default '{}'\n  created_at          timestamptz not null\n```\n\n`system_settings` 只保存非敏感设置；Secret 继续使用 Secret 文件/未来 Secret Provider。Repository 对同 key upsert 时递增 `version`，调用方拥有事务。\n\n`audit_events` 只追加，当前 Repository 不提供更新/删除接口。`actor_kind` 可表达 `system` 和未来 `principal`；第三方身份必须先映射内部 Principal，不能把飞书 `open_id`、`union_id`、Token 或 SDK 对象变成业务主键。\n\n当前仍不建立本地 `users/sessions/auth_login_attempts`。未来 Principal/Role/Permission、第三方认证以及依赖 actor 的 API 幂等 Schema 都在真实认证需求明确后通过独立 L3 Change/Migration 冻结。\n\n""",
    )
    replace_section(
        "docs/blueprint/03-数据库与文件存储.md",
        "## 9. 表写入所有权\n",
        "## 10. Migration",
        """## 9. 表写入所有权\n\n每张已落地表只有一个写 Owner，机器事实维护在 SQLAlchemy `Table.info['owner']`，`scripts/quality/check_table_ownership.py` 在 CI 中校验，禁止另维护一份可能漂移的表名映射。\n\nStage 3A 当前：\n\n| 表 | Owner |\n| --- | --- |\n| `artifacts` | platform |\n| `system_settings` | system |\n| `audit_events` | system |\n\n未来业务表仍按模块边界确定 Owner；跨模块修改必须调用 Owner Service/Repository，禁止复制 SQL 越权写表。角色、Session、API 幂等等未建立表不应出现在“当前 Owner”清单中。\n\n""",
    )
    replace_section(
        "docs/blueprint/03-数据库与文件存储.md",
        "## 10. Migration\n",
        "## 11. 分区和归档",
        """## 10. Migration\n\n所有 Schema 演进使用根目录 `alembic.ini` + `migrations/`。Stage 3A 已建立首条 Revision `20260813_0001`，当前建表仅包括 `artifacts`、`system_settings`、`audit_events`。\n\n规则：\n\n1. 已发布 Revision 禁止改写；后续变化新增 Revision；\n2. API/Worker/Scheduler 启动不自动运行 Migration；Migration 是独立进程/命令；\n3. Table 定义是运行时 Schema/Repository 的机器结构，Revision 显式冻结已批准变化；CI 使用 `alembic check` 防止二者漂移；\n4. 首条 Revision 已在 PostgreSQL 18.4 验证 `base → head → base → head`；未来从上一正式 Revision 升级在第二条 Revision 出现后成为强制门禁；\n5. downgrade 是开发/CI 可逆性证据，不替代生产 Backup Set 与数据回滚设计；\n6. 任何新增表必须同时声明唯一 Owner 并通过 PostgreSQL Integration。\n\n""",
    )
    replace_section(
        "docs/blueprint/03-数据库与文件存储.md",
        "### 12.1 接口\n",
        "### 12.2 本地目录",
        """### 12.1 接口\n\n当前生产接口以代码为准：\n\n```python\nclass ArtifactStore(Protocol):\n    @property\n    def backend_name(self) -> str: ...\n    def put(self, storage_key: str, data: bytes) -> StoredBytes: ...\n    def read(self, storage_key: str) -> bytes: ...\n    def exists(self, storage_key: str) -> bool: ...\n```\n\nStore 只处理 `storage_key` 和字节，不理解 Artifact UUID、数据库或权限。Artifact ID/元数据/生命周期由 `ArtifactService + ArtifactMetadataPort` 管理。删除接口当前故意不开放，因为访问、保留和删除规则仍是 Stage 0 用户决策门禁。\n\n""",
    )
    replace_section(
        "docs/blueprint/03-数据库与文件存储.md",
        "## 13. 保留策略\n",
        "## 14. 备份与恢复",
        """## 13. 保留策略\n\n当前**不冻结具体天数**。Stage 0 仍需用户批准个人信息、Raw、报告/导出、审计等数据的访问、保留、删除与合规规则；因此 Stage 3A 只建立可表达策略的 `retention_class` 与可空 `expires_at`，不自动删除任何业务 Artifact。\n\n后续实现自动清理前至少必须满足：\n\n- 用户已批准各 Retention Class 的具体期限/长期保留规则；\n- 有明确访问权限与下载审计；\n- 清理写审计事件；\n- 不删除仍被业务记录引用的 Artifact；\n- 支持 Dry Run，并先输出预计数量和容量；\n- 清理作为持久化 Job 执行，不在普通 HTTP 请求中执行；\n- 删除/保留动作与备份写屏障、引用检查、恢复方案兼容。\n\n临时工作文件的技术性清理可以按独立运行目录规则处理，但不得借“临时文件”名义删除 Raw、报告、导出或审计业务证据。\n\n""",
    )

    replace_once(
        "docs/blueprint/06-开发约束与分阶段实施.md",
        "### 阶段 3：Contract、数据库与 System/Audit\n\n→ 修改范围：Canonical Pydantic、JSON Schema 生成、核心表、Artifact 元数据 Repository/Table、System Settings、Provider 中立审计、Alembic，以及未来第三方身份接入所需的 `Principal/AuthContext` Port 边界  \n→ 预期结果：空库可升级，示例可校验，表 Owner 明确；认证 Provider 可以未来接入而不污染业务模块；当前不实现登录入口、本地密码、Session、CSRF、登录限流或 MFA  \n→ 验证：Migration 升降级、Contract 生成/兼容、Artifact Repository、审计 actor Provider 中立性和依赖方向；真实飞书/OIDC/Session 安全专项留到认证接入 Change",
        "### 阶段 3：Contract、数据库与 System/Audit\n\n**Stage 3A 数据库基础已完成**：根 Alembic、首条 Revision、`artifacts/system_settings/audit_events`、唯一 Table Owner、Artifact PostgreSQL Metadata Repository、System Settings 与 Provider 中立 Audit Repository 已由 PostgreSQL 18.4 CI 验证 `base → head → base → head` 和 `alembic check`。当前不实现登录入口、本地密码、Session、CSRF、登录限流或 MFA。\n\n**下一步 Stage 3B**：建立 Canonical Pydantic 唯一手写事实源、生成 JSON Schema、固定合法脱敏示例和 Contract Test。只有平台字段/个人信息语义需要业务决定时才按用户决策门禁暂停对应部分。",
    )

    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "> 蓝图版本：1.7  ",
        "> 蓝图版本：1.8  ",
    )
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "| 认证授权 | Session、登录限流、Role/Permission、撤销/过期和审计均有数据库事实；在业务写 API 前实施 |",
        "| 认证授权 | 第一版登录已明确延期；未来身份 Provider 经 Adapter → Principal/AuthContext → Authorization 接入，当前不创建本地 Session/Auth 表 |",
    )
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "需要用户/业务 Owner 决定的事项采用固定门禁：Agent 先调查可自行确认的事实，**在对话中给出推荐方案**，必要时附 2–3 个实质不同备选和影响，再由用户作最终决定。决定前暂停依赖该语义的 Contract/Schema/安全或不可逆实现；用户决定或明确延期后，同一任务必须写入对应领域 Blueprint/需求、OpenSpec（存在时）和当前 Change，形成机器 Contract/Schema 时再同步机器事实。聊天记录不能成为后续实现唯一依据。",
        "需要用户/业务 Owner 决定的事项采用固定门禁：Agent 先调查可自行确认的事实，**在对话中给出推荐方案**，必要时附 2–3 个实质不同备选和影响，再由用户作最终决定。决定前暂停依赖该语义的 Contract/Schema/安全或不可逆实现；用户决定或明确延期后，同一任务必须写入对应领域 Blueprint/需求、OpenSpec（存在时）和当前 Change，形成机器 Contract/Schema 时再同步机器事实。聊天记录不能成为后续实现唯一依据。\n\n### 2.9 Stage 3A 数据库与基础持久化\n\nStage 3A 已建立根 Alembic 运行链和首条 `20260813_0001` Revision。当前应用 Schema 机器注册入口为 `aima_ugc.database_schema`，只包含：\n\n- `artifacts`，Owner=`platform`；\n- `system_settings`，Owner=`system`；\n- `audit_events`，Owner=`system`。\n\n`ArtifactMetadataPort` 已有 PostgreSQL Repository；状态转换使用条件更新，非法/竞争转换关闭失败。System Settings 只保存非敏感 JSON 设置并递增版本；Audit 只追加且 actor 为 `system/principal` Provider 中立语义。\n\nCI 的 `Stage 3A Database` 使用 PostgreSQL 18.4 实际验证空库 upgrade、`alembic check`、Repository 集成、downgrade base、再次 upgrade 和再次 drift check。当前尚无“上一正式 Revision → 新 Revision”场景；第二条 Revision 出现后必须加入该门禁。\n\n保留/删除具体期限仍未决；Stage 3A 不实现自动删除。登录/Session/Principal/Role/Permission/API 幂等 actor Schema 继续按 2.8 延期。",
    )
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "| 数据库 | PostgreSQL | 18.4 | Stage 2 已验证真实连接与 readiness；阶段 3 再验证 Schema/Migration |",
        "| 数据库 | PostgreSQL | 18.4 | Stage 2 已验证连接/readiness；Stage 3A 已验证首条 Schema/Migration 与 Repository |",
    )
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "| 后端 | Alembic | 1.19.1 | `uv.lock` 已锁定；阶段 3 再建立 Revision |",
        "| 后端 | Alembic | 1.19.1 | `uv.lock` 已锁定；Stage 3A 首条 Revision 与升降级/drift 门禁已验证 |",
    )
    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "| 3 Contract/DB/System | **可推进共享基础**：Canonical/表 Owner/Alembic/Artifact 元数据/System/Audit 边界已设计；本地登录/Session 已明确延期，当前只预留 Provider 中立 Principal/AuthContext 边界 | 因旧蓝图自行创建本地密码/Session 表、把业务身份绑定飞书私有字段、在无认证时宣称敏感写 API 可公网生产 |",
        "| 3 Contract/DB/System | **Stage 3A 已完成，下一步 3B**：首条 Alembic、三张基础表、Table Owner、Artifact/System/Audit Repository 已验证；继续建立 Canonical Contract，本地登录/Session 仍延期 | 改写已发布 Revision、绕过 Owner Repository、写死未批准 Retention 期限、因旧蓝图创建本地密码/Session 表 |",
    )

    replace_once(
        "docs/blueprint/README.md",
        "**Stage 1 工程基线和 Stage 2 Platform 基础均已建立。**",
        "**Stage 1 工程基线、Stage 2 Platform 基础和 Stage 3A 数据库基础均已建立。**",
    )
    replace_once(
        "docs/blueprint/README.md",
        "- 隔离 PostgreSQL 18.4 的 Stage 2 Platform CI。",
        "- 隔离 PostgreSQL 18.4 的 Stage 2 Platform CI；\n- Stage 3A 根 Alembic、`20260813_0001`、`artifacts/system_settings/audit_events`、PostgreSQL Repository 和独立 Migration CI。",
    )
    replace_once(
        "docs/blueprint/README.md",
        "### 阶段 3：Contract、数据库与 System/Auth",
        "### 阶段 3：Contract、数据库与 System/Audit",
    )
    replace_once(
        "docs/blueprint/README.md",
        "Stage 2 已完成，不再继续向 Platform 层堆业务能力。下一阶段应建立：",
        "Stage 2 已完成，Stage 3A 数据库/Alembic/基础持久化也已完成。下一步 Stage 3B 应建立：",
    )
    replace_once(
        "docs/blueprint/README.md",
        "- 核心 PostgreSQL Schema 与 Alembic Revision；\n- Artifact 元数据 PostgreSQL Repository / Table，使 Stage 2 的 Metadata Port 有正式实现；\n- System Settings、User、Role、Permission、Session、登录限流、审计；\n- API 幂等基础；\n- 表 Owner、Migration 升降级和隔离 PostgreSQL 集成门禁。",
        "- Canonical Pydantic / JSON Schema 的正式机器 Contract；\n- 固定、合法、脱敏的 Canonical 示例与 Contract Test；\n- Mapper/Ingestion 后续共同消费的稳定字段语义。\n\nStage 3A 已建立的 Schema/Repository 不重复设计；登录、Role/Permission、Principal 和 actor-bound API 幂等继续等待真实第三方身份需求。",
    )


if __name__ == "__main__":
    main()
