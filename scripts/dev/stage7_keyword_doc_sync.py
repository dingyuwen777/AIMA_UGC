from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one old block, found {count}")
    if new in text:
        raise SystemExit(f"{label}: replacement already present before patch")
    path.write_text(text.replace(old, new), encoding="utf-8")


bp03 = Path("docs/blueprint/03-数据库与文件存储.md")
replace_once(
    bp03,
    """priority            integer not null default 100
enabled             boolean not null

primary key(pack_id, keyword_id, platform)
```

`platform='all'` 可以表达全平台词，但创建 Run 时必须展开成明确平台列表。""",
    """priority            integer not null default 100
enabled             boolean not null
note                text not null default ''

primary key(pack_id, keyword_id, platform)
```

`platform='all'` 可以表达全平台词，但创建 Run 时必须展开成明确平台列表。`note` 与 `platform/priority/enabled` 一样是词包内词条的关系属性，不属于全局 `keywords` 身份。""",
    "keyword_pack_items note",
)
replace_once(
    bp03,
    """Stage 3A 当前：

| 表 | Owner |
| --- | --- |
| `artifacts` | platform |
| `system_settings` | system |
| `audit_events` | system |""",
    """当前已落地：

| 表 | Owner |
| --- | --- |
| `artifacts` | platform |
| `system_settings` | system |
| `provider_configs` | system |
| `keyword_packs` | system |
| `keywords` | system |
| `keyword_pack_items` | system |
| `audit_events` | system |""",
    "current table owners",
)
replace_once(
    bp03,
    "所有 Schema 演进使用根目录 `alembic.ini` + `migrations/`。Stage 3A 已建立首条 Revision `20260813_0001`，当前建表仅包括 `artifacts`、`system_settings`、`audit_events`。",
    "所有 Schema 演进使用根目录 `alembic.ini` + `migrations/`。当前 Alembic 链从 `20260813_0001` 演进到 `20260815_0011`；`0011` 新增 `keyword_packs`、`keywords`、`keyword_pack_items`，直接父 Revision 为 `20260815_0010`。",
    "migration current chain",
)
replace_once(
    bp03,
    "4. 首条 Revision 已在 PostgreSQL 18.4 验证 `base → head → base → head`；未来从上一正式 Revision 升级在第二条 Revision 出现后成为强制门禁；",
    "4. 第二条及后续 Revision 必须同时验证上一正式 Revision → head；CI 还应保留 `base → head` 往返验证，不能只验证 `base → head`；",
    "migration verification rule",
)

readme = Path("docs/blueprint/README.md")
replace_once(
    readme,
    "**Stage 1 工程基线、Stage 2 Platform 基础、Stage 3A 数据库基础、Stage 3B Canonical Contract、Stage 4 PostgreSQL Job Runtime、Stage 5A—5D Provider-neutral 基础、Stage 6 小红书纵切，以及 Stage 7 的 Decision/Capability、Provider Config/平台路由与抖音/微博/B站/快手请求分页 Operation 机器基础均已建立。**",
    "**Stage 1 工程基线、Stage 2 Platform 基础、Stage 3A 数据库基础、Stage 3B Canonical Contract、Stage 4 PostgreSQL Job Runtime、Stage 5A—5D Provider-neutral 基础、Stage 6 小红书纵切，以及 Stage 7 的 Decision/Capability、Provider Config/平台路由、关键词/词包父事实与抖音/微博/B站/快手请求分页 Operation 机器基础均已建立。**",
    "readme current stage summary",
)
replace_once(
    readme,
    "- Stage 7 `ProviderConfigV1` / `ProviderPlatformRouteV1`、System `provider_configs`、`20260815_0010`、PostgreSQL Provider Config Repository、Secret 引用校验和当前只登记 `tikhub + xhs` 的 Provider Registry；同一种 Provider 可以有多个配置实例，实例不绑定平台，平台/Plan 后续选择具体 `provider_config_id`；",
    """- Stage 7 `ProviderConfigV1` / `ProviderPlatformRouteV1`、System `provider_configs`、`20260815_0010`、PostgreSQL Provider Config Repository、Secret 引用校验和当前只登记 `tikhub + xhs` 的 Provider Registry；同一种 Provider 可以有多个配置实例，实例不绑定平台，平台/Plan 后续选择具体 `provider_config_id`；
- Stage 7 System `keyword_packs/keywords/keyword_pack_items`、`20260815_0011`、PostgreSQL Keyword Catalog Repository，以及 `normalized_text` 唯一、关系复合主键/外键和 System Owner 约束；""",
    "readme machine facts bullet",
)
replace_once(
    readme,
    "System `provider_configs`/Repository、`adapters/providers/registry.py`",
    "System `provider_configs`/Repository、System `keyword_packs/keywords/keyword_pack_items` 与 `adapters/persistence/postgres/keywords.py`、`adapters/providers/registry.py`",
    "readme stage7 source list",
)
replace_once(
    readme,
    "`contracts/collection/`、第十条 Revision、对应测试和 CI 为准。",
    "`contracts/collection/`、第十至第十一条 Revision、对应测试和 CI 为准。",
    "readme stage7 revision range",
)
replace_once(
    readme,
    "- Provider Config/Platform Route Contract、`provider_configs` System 父事实、PostgreSQL Repository、Secret 引用边界和当前 `tikhub + xhs` Provider Registry；",
    """- Provider Config/Platform Route Contract、`provider_configs` System 父事实、PostgreSQL Repository、Secret 引用边界和当前 `tikhub + xhs` Provider Registry；
- `keyword_packs/keywords/keyword_pack_items` System 父事实、PostgreSQL Keyword Catalog Repository、`20260815_0011` 及唯一/外键/复合主键约束；""",
    "readme completed keyword unit",
)
replace_once(
    readme,
    "- 关键词/词包、Plan 平台配置、Occurrence 与 Run Snapshot 等剩余父事实；",
    "- Plan 平台配置、Occurrence 与 Run Snapshot 等剩余父事实；",
    "readme remaining parent facts",
)
