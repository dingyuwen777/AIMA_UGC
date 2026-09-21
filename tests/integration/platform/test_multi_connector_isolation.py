"""多企业的**真实 PostgreSQL** 集成测试（跨企业隔离与串号防护）。

════════ 这个文件证明什么 ════════

单测（`test_feishu_connector.py`）只证明"配置对象算得对"。
**本文件用真实 PostgreSQL 证明"身份在库里真的隔离"**：

| 测试 | 守住的静默故障 |
|---|---|
| 同一人在两家企业 → 两条映射 | 只靠唯一约束；不实测就不知道它是否真的按 `connector_id` 分组 |
| 两家的 `sessions` 互不干扰 | 会话是否真的按 principal 隔离 |
| **`state` 跨企业串号被拒** | 用 A 的 state 走 B 的回调 —— **安全关键** |
| 单企业形态不受影响 | 改造不能破坏既有数据 |

⚠️ 这些断言**必须跑在真实 PostgreSQL 上** —— 唯一约束、`RETURNING`、
`timestamptz` 比较都是 PostgreSQL 语义，SQLite 证明不了。
"""

from __future__ import annotations

import os
from datetime import timedelta
from uuid import uuid4

import pytest
from aima_ugc.modules.identity.feishu.principal_store import PrincipalStore
from aima_ugc.modules.identity.feishu.session_store import SessionStore
from aima_ugc.modules.identity.tables import (
    identity_external_identities_table,
    identity_login_states_table,
    identity_principals_table,
)
from aima_ugc.platform.database.metadata import metadata
from aima_ugc.platform.time import beijing_now
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session, sessionmaker

# 两家企业的 `connector_id`（真实派生值）。
# ⚠️ NNIT 的那个是**生产环境的真实值**，不能改。
NNIT_CONNECTOR_ID = "7d88a4816c7a5e07a95ca3c2012fb2f7"
AIMA_CONNECTOR_ID = "11a7d3d755bb5e4fb4aa4584f4d949bd"


@pytest.fixture
def pg_session() -> Session:
    """用环境里的 PostgreSQL 建库并返回 Session；无库时跳过。"""

    host = os.environ.get("AIMA_DB_HOST")
    port = os.environ.get("AIMA_DB_PORT")
    if not host or not port:
        pytest.skip("未提供 AIMA_DB_HOST / AIMA_DB_PORT，跳过真实 SQL 校验")

    url = (
        f"postgresql+psycopg://{os.environ.get('AIMA_DB_USER', 'aima_ugc')}:"
        f"{_pg_password()}@{host}:{port}/{os.environ.get('AIMA_DB_NAME', 'aima_ugc')}"
    )
    engine = create_engine(url)
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _pg_password() -> str:
    """从 Secret 文件读测试库密码。"""

    from pathlib import Path

    secret_dir = os.environ.get("AIMA_SECRET_DIR")
    if secret_dir:
        path = Path(secret_dir) / "postgres_password"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return "ci-postgres"


# ═══════════════ ① 同一人在两家企业 → 两条独立身份 ═══════════════
def test_same_person_in_two_enterprises_gets_two_principals(pg_session: Session) -> None:
    """**同一自然人**在两家企业登录 → **两条映射、两个 Principal**，互不覆盖。

    这是"多企业共用一套数据"的核心不变量：飞书的身份边界即企业，
    同一个人号在两家企业是**两个员工身份**，系统不去猜它们是不是同一人。
    """

    shared_subject = f"on_shared_{uuid4().hex}"
    store = PrincipalStore(pg_session)

    nnit_principal = store.resolve_or_create(
        connector_id=NNIT_CONNECTOR_ID,
        provider="feishu",
        provider_subject=shared_subject,
        display_name="张三（NNIT）",
    )
    aima_principal = store.resolve_or_create(
        connector_id=AIMA_CONNECTOR_ID,
        provider="feishu",
        provider_subject=shared_subject,
        display_name="张三（爱玛）",
    )
    pg_session.commit()

    # 两个**不同**的 AIMA 内部身份
    assert nnit_principal.principal_id != aima_principal.principal_id

    # 库里确实是两条映射（唯一约束按 connector_id 分组）
    rows = (
        pg_session.execute(
            select(identity_external_identities_table).where(
                identity_external_identities_table.c.provider_subject == shared_subject
            )
        )
        .mappings()
        .all()
    )
    assert len(rows) == 2
    assert {row["connector_id"] for row in rows} == {NNIT_CONNECTOR_ID, AIMA_CONNECTOR_ID}


def test_same_enterprise_same_subject_reuses_principal(pg_session: Session) -> None:
    """**同一企业**内同一身份重复登录 → **复用**同一个 Principal（不重复建）。"""

    subject = f"on_same_{uuid4().hex}"
    store = PrincipalStore(pg_session)

    first = store.resolve_or_create(
        connector_id=NNIT_CONNECTOR_ID,
        provider="feishu",
        provider_subject=subject,
        display_name="李四",
    )
    second = store.resolve_or_create(
        connector_id=NNIT_CONNECTOR_ID,
        provider="feishu",
        provider_subject=subject,
        display_name="李四",
    )
    pg_session.commit()

    assert first.principal_id == second.principal_id
    # 只应有一条映射
    count = len(
        pg_session.execute(
            select(identity_external_identities_table).where(
                identity_external_identities_table.c.provider_subject == subject
            )
        )
        .mappings()
        .all()
    )
    assert count == 1


# ═══════════════ ② 会话按身份隔离 ═══════════════
def test_sessions_are_isolated_per_principal(pg_session: Session) -> None:
    """两家企业的会话挂在**各自的** Principal 上，撤销一家不影响另一家。"""

    subject = f"on_sess_{uuid4().hex}"
    store = PrincipalStore(pg_session)
    nnit = store.resolve_or_create(
        connector_id=NNIT_CONNECTOR_ID,
        provider="feishu",
        provider_subject=subject,
        display_name="王五（NNIT）",
    )
    aima = store.resolve_or_create(
        connector_id=AIMA_CONNECTOR_ID,
        provider="feishu",
        provider_subject=subject,
        display_name="王五（爱玛）",
    )
    pg_session.commit()

    sessions = SessionStore(pg_session)
    nnit_token = sessions.issue(
        principal_id=nnit.principal_id,
        display_name=nnit.display_name,
        role="administrator",
        avatar_url=None,
        department_id=None,
        department_name=None,
        feishu_group_ids=("g1",),
        ttl=timedelta(hours=1),
    )
    aima_token = sessions.issue(
        principal_id=aima.principal_id,
        display_name=aima.display_name,
        role="user",
        avatar_url=None,
        department_id=None,
        department_name=None,
        feishu_group_ids=("g2",),
        ttl=timedelta(hours=1),
    )
    pg_session.commit()

    # 撤销 NNIT 的会话，爱玛的不受影响
    assert sessions.revoke(nnit_token) is True
    pg_session.commit()

    nnit_record = sessions.find(nnit_token)
    aima_record = sessions.find(aima_token)
    assert nnit_record is not None and nnit_record.revoked_at is not None
    assert aima_record is not None and aima_record.revoked_at is None


# ═══════════════ ③ ★ state 跨企业串号防护（安全关键）═══════════════
def test_state_records_connector_id(pg_session: Session) -> None:
    """`state` 落库时带 `connector_id` —— 这是串号校验的前提。"""

    from aima_ugc.bootstrap.feishu_auth_http import _LoginStateStore

    _LoginStateStore(pg_session).issue(
        return_to="/",
        ttl=timedelta(minutes=10),
        client_ip="1.2.3.4",
        connector_id=AIMA_CONNECTOR_ID,
    )
    pg_session.commit()

    # 直接查库：最新那条应带 aima 的 connector_id
    row = (
        pg_session.execute(
            select(identity_login_states_table)
            .order_by(identity_login_states_table.c.created_at.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    assert row is not None
    assert row["connector_id"] == AIMA_CONNECTOR_ID


def test_cross_connector_state_is_rejected(pg_session: Session) -> None:
    """🔴 **用 A 企业的 state 走 B 企业的回调 → 必须拒绝**。

    这是纵深防御：即使配置写错（两家 Secret 配成同一个），这一层也能拦住串号。
    """

    from aima_ugc.bootstrap.feishu_auth_http import LoginStateInvalid, _LoginStateStore

    store = _LoginStateStore(pg_session)
    # 用 **aima** 签发 state
    state = store.issue(
        return_to="/voice-plaza",
        ttl=timedelta(minutes=10),
        client_ip=None,
        connector_id=AIMA_CONNECTOR_ID,
    )
    pg_session.commit()

    # 拿它去打 **nnit** 的回调（expected 是 nnit 的 connector_id）
    with pytest.raises(LoginStateInvalid) as exc:
        store.consume(state, expected_connector_id=NNIT_CONNECTOR_ID)
    assert exc.value.reason == "connector_mismatch"


def test_matching_connector_state_is_accepted(pg_session: Session) -> None:
    """**同企业**的 state 正常通过（防护不能误伤正常流程）。"""

    from aima_ugc.bootstrap.feishu_auth_http import _LoginStateStore

    store = _LoginStateStore(pg_session)
    state = store.issue(
        return_to="/voice-plaza",
        ttl=timedelta(minutes=10),
        client_ip=None,
        connector_id=AIMA_CONNECTOR_ID,
    )
    pg_session.commit()

    result = store.consume(state, expected_connector_id=AIMA_CONNECTOR_ID)
    assert result == "/voice-plaza"


def test_single_enterprise_state_skips_connector_check(pg_session: Session) -> None:
    """**单企业形态**（state 里没有 connector）→ 跳过校验，**旧行为不变**。"""

    from aima_ugc.bootstrap.feishu_auth_http import _LoginStateStore

    store = _LoginStateStore(pg_session)
    # 单企业：connector_id 传 None（与改造前一致）
    state = store.issue(
        return_to="/",
        ttl=timedelta(minutes=10),
        client_ip=None,
        connector_id=None,
    )
    pg_session.commit()

    # 即使传入 expected，也因"签发时没记企业"而放过 —— 兼容性保证
    assert store.consume(state, expected_connector_id=AIMA_CONNECTOR_ID) == "/"


def test_state_is_consumed_once_even_on_mismatch(pg_session: Session) -> None:
    """串号尝试**也会消费掉 state**（不让它还能被重放）。

    ⚠️ 这是刻意的设计：校验发生在 UPDATE 之后（一条语句原子完成消费与读取），
    所以"被拒绝的那次"已经把 state 标记为已消费。
    """

    from aima_ugc.bootstrap.feishu_auth_http import LoginStateInvalid, _LoginStateStore

    store = _LoginStateStore(pg_session)
    state = store.issue(
        return_to="/",
        ttl=timedelta(minutes=10),
        client_ip=None,
        connector_id=AIMA_CONNECTOR_ID,
    )
    pg_session.commit()

    with pytest.raises(LoginStateInvalid):
        store.consume(state, expected_connector_id=NNIT_CONNECTOR_ID)

    # 再试一次（用正确的企业）—— 应报"已消费/不存在"，而不是成功
    with pytest.raises(LoginStateInvalid):
        store.consume(state, expected_connector_id=AIMA_CONNECTOR_ID)


# ═══════════════ ④ 唯一约束确实按 connector_id 分组 ═══════════════
def test_unique_constraint_groups_by_connector(pg_session: Session) -> None:
    """直接验唯一约束的行为：同企业内重复 冲突；跨企业 不冲突。

    ⚠️ 这条是**数据库层**的证明 —— 应用层"我以为唯一约束会分组"不算数。
    """

    subject = f"on_uniq_{uuid4().hex}"
    table = identity_external_identities_table

    principal_a = uuid4().hex
    principal_b = uuid4().hex
    now = beijing_now()
    pg_session.execute(
        insert(identity_principals_table).values(
            [
                {"id": principal_a, "display_name": "A", "created_at": now, "updated_at": now},
                {"id": principal_b, "display_name": "B", "created_at": now, "updated_at": now},
            ]
        )
    )
    pg_session.flush()

    # 跨企业：同一 subject 可以共存
    pg_session.execute(
        insert(table).values(
            [
                {
                    "id": uuid4().hex,
                    "principal_id": principal_a,
                    "connector_id": NNIT_CONNECTOR_ID,
                    "provider": "feishu",
                    "provider_subject": subject,
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "id": uuid4().hex,
                    "principal_id": principal_b,
                    "connector_id": AIMA_CONNECTOR_ID,
                    "provider": "feishu",
                    "provider_subject": subject,
                    "created_at": now,
                    "updated_at": now,
                },
            ]
        )
    )
    pg_session.commit()

    # 同企业内：再来一条同 (connector, subject) 必须冲突
    #
    # ⚠️ 冲突**在 execute 时就抛出**（SQLAlchemy 立即 flush），不是在 commit 时 ——
    # 所以 `pytest.raises` 要包住 `execute` 这一句。
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        pg_session.execute(
            insert(table).values(
                id=uuid4().hex,
                principal_id=principal_a,
                connector_id=NNIT_CONNECTOR_ID,
                provider="feishu",
                provider_subject=subject,
                created_at=now,
                updated_at=now,
            )
        )
        pg_session.flush()
    pg_session.rollback()
