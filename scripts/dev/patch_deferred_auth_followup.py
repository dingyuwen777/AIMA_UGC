"""一次性清理第三方身份延期决定后的剩余旧认证假设。"""

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:100]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_section(path: str, start: str, end: str, replacement: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError(f"{path}: section markers are not unique")
    before, tail = text.split(start, 1)
    _, after = tail.split(end, 1)
    file_path.write_text(before + replacement + end + after, encoding="utf-8")


def main() -> None:
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "- 身份验证和权限；",
        "- 第三方身份接入后，通过统一 `Principal/AuthContext` 执行后端权限校验；当前第一版不实现登录入口；",
    )
    replace_once(
        "docs/blueprint/01-总体架构与技术选型.md",
        "| `system` | 用户、角色/权限、Session、登录限流、API 幂等、关键词包、Provider 非敏感配置、审计 | 配置、认证和权限结果 |",
        "| `system` | System Settings、关键词包、Provider 非敏感配置、Provider 中立审计；未来第三方身份通过 Adapter → Principal/AuthContext → Permission 扩展 | 配置、审计和未来授权边界 |",
    )

    replace_section(
        "docs/blueprint/04-后端任务API与前端.md",
        "### 4.6 幂等\n",
        "### 4.7 身份认证扩展边界与授权",
        """### 4.6 幂等

HTTP 写请求的幂等仍是长期要求，但现有语义以稳定 actor/Principal 为作用域。当前第一版已明确延期认证，Principal/actor 数据库语义尚未冻结，因此 Stage 3A **不创建绑定 `users` 的 `api_idempotency_records`**，也不为了实现幂等反向引入本地用户表。

未来进入真实认证/写 API 阶段时，再在同一个 L3 Change 中冻结：

- actor/Principal 的稳定内部作用域；
- `Idempotency-Key` 有效期；
- operation 标识和规范化 Payload Hash；
- 同 actor + operation + key + 同 Payload 返回原结果；
- 同作用域/key 但 Payload 不同返回 409；
- 过期复用、审计、清理和索引；
- API 幂等记录、业务资源与下游 Job 的同事务边界。

API 幂等与 Job 内部 `job_type + internal_idempotency_key` 始终是两个不同契约，不因认证延期而合并。

""",
    )

    replace_once(
        "docs/blueprint/05-日志安全部署与运维.md",
        "以下操作必须写 `audit_events`，不能只写轮转日志：",
        "以下操作在对应能力存在时必须写 `audit_events`，不能只写轮转日志；登录/用户/角色相关项当前尚未实现，只约束未来认证接入：",
    )

    replace_once(
        "docs/blueprint/07-技术决策与实施门禁.md",
        "| 8 API/前端 | Auth/API 幂等/统一错误/Cursor 契约已验证 | 只靠前端隐藏按钮授权 |",
        "| 8 API/前端 | 统一错误/Cursor/页面所需 Contract 已验证；若届时接入第三方认证，则 Principal/Permission/对象级授权和 API 幂等 actor 语义必须一并验收；未接入时只允许受控环境开发，不得宣称公网生产认证成立 | 用 Mock 登录冒充真实认证、只靠前端隐藏按钮授权、在 actor 语义未定时硬编码本地 users 幂等外键 |",
    )


if __name__ == "__main__":
    main()
