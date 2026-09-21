"""身份映射与 AIMA 会话的 PostgreSQL 集成回归。

覆盖任务书 DoD：

    D6  UNIQUE(connector_id, provider_subject) 真的生效
    D7  role 的 CHECK 约束真的拦非法值
    D8  同一 provider_subject 重复登录 → 复用同一 principal_id（不新建）
    D9  会话只存 hash：库里查不到明文 token

**全部连真实 PostgreSQL**（`load_settings()` 提供的库），不使用 SQLite 或内存替身 ——
约束是数据库自己的行为，用替身测等于没测。
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from aima_ugc.modules.identity.feishu import (
    PrincipalStore,
    SessionStore,
    hash_session_token,
)
from aima_ugc.modules.identity.tables import (
    identity_external_identities_table,
    identity_principals_table,
    identity_sessions_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

PROVIDER = "feishu"
SUBJECT = "on_unit_test_union_id_0001"


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    """真实 PostgreSQL 会话工厂；用例前后清空本单涉及的 3 张表。"""

    runtime = DatabaseRuntime(load_settings())

    def cleanup() -> None:
        with runtime.engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE TABLE identity_sessions, identity_external_identities, "
                    "identity_principals RESTART IDENTITY CASCADE"
                )
            )

    cleanup()
    try:
        yield sessionmaker(bind=runtime.engine, class_=Session, expire_on_commit=False)
    finally:
        cleanup()
        runtime.dispose()


def _count(session: Session, table: object) -> int:
    """数一张表的行数（`select_from` 显式给表，避免 count 绑到错误的 FROM）。"""

    return int(session.scalar(select(func.count()).select_from(table)) or 0)


# ------------------------------------------------------------------ D8 映射语义
def test_d8_repeated_login_reuses_the_same_principal(
    session_factory: sessionmaker[Session],
) -> None:
    """同一 provider_subject 登录两次 → 同一个 principal_id，且只建了 1 个 Principal。"""

    connector_id = uuid4().hex
    with session_factory() as session, session.begin():
        store = PrincipalStore(session)
        first = store.resolve_or_create(
            connector_id=connector_id,
            provider=PROVIDER,
            provider_subject=SUBJECT,
            display_name="张三",
        )

    with session_factory() as session, session.begin():
        store = PrincipalStore(session)
        second = store.resolve_or_create(
            connector_id=connector_id,
            provider=PROVIDER,
            provider_subject=SUBJECT,
            display_name="张三（改名了）",
        )
        assert _count(session, identity_principals_table) == 1, "重复登录不得新建 Principal"
        assert _count(session, identity_external_identities_table) == 1, "不得重复写映射"

    assert first.created is True, "首次登录应当报告 created=True"
    assert second.created is False, "第二次登录必须复用，不能报新建"
    assert first.principal_id == second.principal_id, "两次登录必须拿到同一个 principal_id"
    # 已有 Principal 的名称不被外部身份静默改名。
    assert second.display_name == "张三"


def test_d8_same_subject_in_a_different_connector_is_a_different_principal(
    session_factory: sessionmaker[Session],
) -> None:
    """不同企业（connector）是不同身份域：同一个人也**不自动合并账户**。

    这是原方案明确要求的行为（"第一版也不要自动猜测合并账户"）。
    """

    with session_factory() as session, session.begin():
        store = PrincipalStore(session)
        company_a = store.resolve_or_create(
            connector_id=uuid4().hex,
            provider=PROVIDER,
            provider_subject=SUBJECT,
            display_name="张三",
        )
        company_b = store.resolve_or_create(
            connector_id=uuid4().hex,
            provider=PROVIDER,
            provider_subject=SUBJECT,
            display_name="张三",
        )
        assert _count(session, identity_principals_table) == 2

    assert company_a.principal_id != company_b.principal_id


# ------------------------------------------------- D6 唯一约束（真的由数据库拦）
def test_d6_duplicate_connector_subject_is_rejected_by_the_database(
    session_factory: sessionmaker[Session],
) -> None:
    """同一 (connector_id, provider_subject) 插第二条映射 → 数据库报冲突。

    这里**绕过 Store 直接写表**：要验的是「数据库约束真的存在并生效」，
    而不是「Store 恰好没写第二条」。
    """

    connector_id = uuid4().hex
    with session_factory() as session, session.begin():
        store = PrincipalStore(session)
        owner = store.resolve_or_create(
            connector_id=connector_id,
            provider=PROVIDER,
            provider_subject=SUBJECT,
            display_name="张三",
        )
        other = store.resolve_or_create(
            connector_id=connector_id,
            provider=PROVIDER,
            provider_subject="on_another_subject",
            display_name="李四",
        )

    from aima_ugc.platform.time import beijing_now

    now = beijing_now()
    with pytest.raises(IntegrityError) as excinfo:
        with session_factory() as session, session.begin():
            session.execute(
                identity_external_identities_table.insert().values(
                    id=uuid4().hex,
                    principal_id=other.principal_id,
                    connector_id=connector_id,
                    provider=PROVIDER,
                    # 与第一条**完全相同**的外部身份 → 必须被唯一约束拒绝。
                    provider_subject=SUBJECT,
                    created_at=now,
                    updated_at=now,
                    last_seen_at=now,
                )
            )
    assert "uq_identity_external_identities" in str(excinfo.value) or (
        "unique" in str(excinfo.value).lower()
    )

    with session_factory() as session:
        assert _count(session, identity_external_identities_table) == 2, "冲突的那条不得落库"

    # 顺便确认赢家仍是原 Principal：唯一约束保护的正是"一个身份只映射一个 Principal"。
    assert owner.principal_id != other.principal_id


# ------------------------------------------------------- D7 角色 CHECK 真的拦非法值
@pytest.mark.parametrize("invalid_role", ["super_admin", "Administrator", "", "admin"])
def test_d7_invalid_role_is_rejected_by_the_check_constraint(
    session_factory: sessionmaker[Session], invalid_role: str
) -> None:
    """role 只允许 administrator / user；其它值（含大小写不同的）必须被数据库拦下。"""

    with session_factory() as session, session.begin():
        principal = PrincipalStore(session).resolve_or_create(
            connector_id=uuid4().hex,
            provider=PROVIDER,
            provider_subject=SUBJECT,
            display_name="张三",
        )

    from aima_ugc.platform.time import beijing_now

    now = beijing_now()
    with pytest.raises(IntegrityError) as excinfo:
        with session_factory() as session, session.begin():
            session.execute(
                identity_sessions_table.insert().values(
                    token_hash=hash_session_token("some-token-value"),
                    principal_id=principal.principal_id,
                    display_name="张三",
                    role=invalid_role,
                    issued_at=now,
                    expires_at=now,
                    last_seen_at=now,
                )
            )
    assert "ck_identity_sessions_role_allowed" in str(excinfo.value)

    with session_factory() as session:
        assert _count(session, identity_sessions_table) == 0


def test_d7_administrator_and_user_are_both_accepted(
    session_factory: sessionmaker[Session],
) -> None:
    """两个合法角色都能落库（证明上一条不是因为"写不进任何数据"而通过）。"""

    with session_factory() as session, session.begin():
        principal = PrincipalStore(session).resolve_or_create(
            connector_id=uuid4().hex,
            provider=PROVIDER,
            provider_subject=SUBJECT,
            display_name="张三",
        )
        sessions = SessionStore(session)
        for role in ("administrator", "user"):
            sessions.issue(
                principal_id=principal.principal_id,
                display_name="张三",
                role=role,
            )
        assert _count(session, identity_sessions_table) == 2


# ------------------------------------------------------------ D9 会话只存 hash
def test_d9_plaintext_session_token_is_never_stored(
    session_factory: sessionmaker[Session],
) -> None:
    """库里**查不到明文 token**；能按 hash 查到，且明文不进任何列。"""

    with session_factory() as session, session.begin():
        principal = PrincipalStore(session).resolve_or_create(
            connector_id=uuid4().hex,
            provider=PROVIDER,
            provider_subject=SUBJECT,
            display_name="张三",
        )
        token = SessionStore(session).issue(
            principal_id=principal.principal_id,
            display_name="张三",
            role="administrator",
        )

    assert token, "issue() 必须返回明文令牌给调用方放进 Cookie"

    with session_factory() as session:
        # ① 用**明文**当 token_hash 查 → 一定查不到。
        by_plaintext = session.scalar(
            select(identity_sessions_table.c.principal_id).where(
                identity_sessions_table.c.token_hash == token
            )
        )
        assert by_plaintext is None, "明文 token 出现在 token_hash 列 = 严重安全问题"
        assert _count(session, identity_sessions_table) == 1

        # ② 用正确的 hash 查 → 查得到（证明"查不到"不是因为表里没数据）。
        by_hash = SessionStore(session).find(token)
        assert by_hash is not None
        assert by_hash.principal_id == principal.principal_id
        assert by_hash.role == "administrator"
        assert by_hash.is_usable(now=by_hash.last_seen_at) is True

        # ③ 明文 token 也不得出现在任何一列里（逐列扫，不只看 token_hash）。
        row = session.execute(select(identity_sessions_table)).mappings().one()
        assert all(token not in str(value) for value in row.values()), "明文 token 泄漏到了别的列"


def test_d9_session_hash_column_rejects_a_plaintext_length_value(
    session_factory: sessionmaker[Session],
) -> None:
    """`token_hash` 有 64 位 CHECK：直接把明文写进去会被数据库拒绝。"""

    with session_factory() as session, session.begin():
        principal = PrincipalStore(session).resolve_or_create(
            connector_id=uuid4().hex,
            provider=PROVIDER,
            provider_subject=SUBJECT,
            display_name="张三",
        )

    from aima_ugc.platform.time import beijing_now

    now = beijing_now()
    with pytest.raises(IntegrityError) as excinfo:
        with session_factory() as session, session.begin():
            session.execute(
                identity_sessions_table.insert().values(
                    token_hash="this-is-a-plaintext-token",
                    principal_id=principal.principal_id,
                    display_name="张三",
                    role="user",
                    issued_at=now,
                    expires_at=now,
                    last_seen_at=now,
                )
            )
    assert "ck_identity_sessions_token_hash_sha256" in str(excinfo.value)


# --------------------------------------------------------------- 会话生命周期
def test_session_revocation_is_server_side(session_factory: sessionmaker[Session]) -> None:
    """登出是服务端失效：撤销后 `find()` 仍能查到记录，但判定为不可用。"""

    with session_factory() as session, session.begin():
        principal = PrincipalStore(session).resolve_or_create(
            connector_id=uuid4().hex,
            provider=PROVIDER,
            provider_subject=SUBJECT,
            display_name="张三",
        )
        store = SessionStore(session)
        token = store.issue(
            principal_id=principal.principal_id,
            display_name="张三",
            role="user",
        )
        assert store.revoke(token) is True
        assert store.revoke(token) is False, "重复登出不应再次计入撤销"

    with session_factory() as session:
        record = SessionStore(session).find(token)
        assert record is not None
        assert record.revoked_at is not None
        assert record.is_usable(now=record.last_seen_at) is False


def test_d8_concurrent_first_login_creates_exactly_one_principal(
    session_factory: sessionmaker[Session],
) -> None:
    """**并发**首次登录同一身份：只能建 1 个 Principal，两个人拿到同一个 ID。

    为什么必须有这条：`resolve_or_create` 的"查→建"之间有窗口。若只是顺序执行，
    普通用例（`test_d8_repeated_login_reuses_the_same_principal`）**永远发现不了**
    并发缺陷 —— 它必须由真的两个连接同时抢。
    """

    from threading import Barrier, Thread

    connector_id = uuid4().hex
    barrier = Barrier(2)
    results: list[tuple[UUID, bool]] = []
    errors: list[BaseException] = []

    def worker() -> None:
        """一个并发登录者：等两人都就位后，同时开始"查→建"。"""

        try:
            with session_factory() as session, session.begin():
                barrier.wait(timeout=10)
                resolved = PrincipalStore(session).resolve_or_create(
                    connector_id=connector_id,
                    provider=PROVIDER,
                    provider_subject=SUBJECT,
                    display_name="并发张三",
                )
                results.append((resolved.principal_id, resolved.created))
        except BaseException as exc:  # noqa: BLE001 - 要把线程里的异常带回主线程
            errors.append(exc)

    threads = [Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == [], f"并发登录不得抛异常给调用方：{errors}"
    assert len(results) == 2, results
    assert len({principal_id for principal_id, _ in results}) == 1, (
        "并发首次登录必须收敛到同一个 principal_id"
    )
    # 恰好一方报告"我建的"，另一方复用 —— 不能两边都以为自己是新建者。
    assert sorted(created for _, created in results) == [False, True]

    with session_factory() as session:
        assert _count(session, identity_principals_table) == 1, "并发下不得留下孤儿 Principal"
        assert _count(session, identity_external_identities_table) == 1
