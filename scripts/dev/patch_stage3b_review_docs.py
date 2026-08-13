"""一次性修正 Stage 3B 文档 Review 发现的事实问题。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: 旧文本必须唯一")
    target.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    replace_once(
        "docs/blueprint/03-数据库与文件存储.md",
        "`provider_request_attempts` 保存每一次真实 HTTP 调用。失败重试不能覆盖上一轮 HTTP 状态、费用或 Raw。",
        "`provider_request_attempts` 保存每一次真实 Provider 执行。HTTP/SDK Provider 的一次外部发送、文件/历史导入的一次受控读取分别形成独立 Attempt；HTTP 状态只在适用时填写。失败重试不能覆盖上一轮执行状态、费用或 Raw。",
    )
    replace_once(
        "docs/blueprint/03-数据库与文件存储.md",
        "`account_external_ids` 关系化保存 `red_id`、`sec_uid`、`bvid/aid` 类备用稳定账号标识；",
        "`account_external_ids` 关系化保存 `red_id`、`sec_uid`、B站账号 `mid`、快手用户 ID 等备用稳定账号标识；",
    )
    replace_once(
        "docs/blueprint/03-数据库与文件存储.md",
        "canonical_identity  text\ntarget_type         text",
        "canonical_identity  text\nobserved_fields     jsonb not null default '[]'\ntarget_type         text",
    )
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "| UGC Provider | `ContentProvider` | TikHub | 其他商业 API、自研采集器 |",
        "| UGC Provider | `ContentProvider` | TikHub（首个参考实现） | 官方 API、Apify、自建采集器、文件/历史导入 |",
    )
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "| 认证 | `AuthProvider` | 本地账号 | 飞书、OIDC |",
        "| 认证 | `Identity/Auth Adapter` | 当前未实现，登录已延期 | 飞书、OIDC、其他企业身份源 |",
    )
    replace_once(
        "docs/blueprint/04-后端任务API与前端.md",
        "```text\nVue Page\n→ Feature Store\n→ Feature API\n→ OpenAPI 生成 Client\n→ FastAPI Router\n→ Application Service\n→ Repository / Provider Port\n→ PostgreSQL 或创建 Job\n```",
        "```text\n读取：\nVue Page\n→ Feature Store / Feature API\n→ OpenAPI 生成 Client\n→ FastAPI Router\n→ Query/Application Service\n→ Query Repository / Read Model\n→ PostgreSQL\n\n写入：\nVue Page\n→ Feature Store / Feature API\n→ OpenAPI 生成 Client\n→ FastAPI Router\n→ Application Service\n→ Owner Repository 或创建 Job\n→ PostgreSQL\n```",
    )
    replace_once(
        "docs/blueprint/04-后端任务API与前端.md",
        "- SQLAlchemy 2 `select()`；",
        "- SQLAlchemy 2 `select()` / `insert()` / `update()` 等显式语句；Query Repository 只使用只读查询；",
    )
    print("Stage 3B Review 文档修正完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
