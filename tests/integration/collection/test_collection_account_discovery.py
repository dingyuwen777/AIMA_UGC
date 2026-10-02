"""账号任务的正式创建、冻结目标与运行中心纵向验证。"""

import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.providers.tikhub import runtime as tikhub_runtime
from aima_ugc.bootstrap.collection_http import PostgresCollectionHttpService
from aima_ugc.contracts.http import CollectionRunCreateRequest, CollectionRuntimeListQuery
from aima_ugc.entrypoints.worker_main import create_collection_job_registry, create_job_worker
from aima_ugc.modules.collection.providers import ProviderTransportResponse
from aima_ugc.modules.collection.tables import collection_runs_table, collection_scopes_table
from aima_ugc.modules.content.tables import (
    comment_coverage_observations_table,
    comments_table,
    contents_table,
)
from aima_ugc.platform.time import beijing_now
from pydantic import SecretStr
from sqlalchemy import func, select

from tests.integration.collection.test_stage8e_collection_http_runtime import (
    _seed_config_and_search_pack,
)
from tests.integration.collection.test_stage8e_collection_http_runtime import (
    runtime as postgres_runtime,
)

runtime = postgres_runtime


def test_four_accounts_create_independent_scopes_and_frozen_v5_runtime(runtime):  # type: ignore[no-untyped-def]
    config_id, _ = _seed_config_and_search_pack(runtime)
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"a" * 32)
    accounts = (
        {"platform": "xiaohongshu", "account_id_type": "red_id", "account_id": "red-1"},
        {"platform": "xiaohongshu", "account_id_type": "user_id", "account_id": "user-2"},
        {"platform": "douyin", "account_id_type": "unique_id", "account_id": "dy-1"},
        {"platform": "weibo", "account_id_type": "uid", "account_id": "123"},
    )
    request = CollectionRunCreateRequest(
        mode="account_discovery",
        account_selection={
            "kind": "accounts",
            "accounts": accounts,
            "published_from": "2026-10-01T00:00:00+08:00",
            "published_to": "2026-10-02T23:59:59+08:00",
        },
        platforms=tuple(
            {"platform": platform, "provider_config_id": config_id}
            for platform in ("xiaohongshu", "douyin", "weibo")
        ),
    )
    created = service.create_run(request, request_id="account-four-scopes")
    with runtime.database.new_session() as session:
        run = (
            session.execute(
                select(collection_runs_table).where(collection_runs_table.c.id == created.run_id)
            )
            .mappings()
            .one()
        )
        scopes = (
            session.execute(
                select(collection_scopes_table).where(
                    collection_scopes_table.c.run_id == created.run_id
                )
            )
            .mappings()
            .all()
        )
    assert len(scopes) == 4
    assert {(scope["platform"], scope["source_value"]) for scope in scopes} == {
        ("xiaohongshu", "red_id:red-1"),
        ("xiaohongshu", "user_id:user-2"),
        ("douyin", "unique_id:dy-1"),
        ("weibo", "uid:123"),
    }
    assert all(
        scope["source_type"] == "account" and scope["operation_group"] == "content_discovery"
        for scope in scopes
    )
    snapshot = run["config_snapshot"]
    assert snapshot["schema_version"] == "collection-run-config.v5"
    assert snapshot["account_selection"] == request.account_selection.model_dump(mode="json")
    assert snapshot["decision_policy"]["full_fetch_threshold"] == 500
    assert snapshot["decision_policy"]["sample_target"] == 500
    assert snapshot["decision_policy"]["reply_target_per_root"] == 30
    assert snapshot["include_comments"] and snapshot["include_sub_comments"]
    assert snapshot["brand_vehicle_filter"]["search_semantics"] == "not_applicable"
    assert len(snapshot["platforms"]) == 3
    assert all(item["config"] == {} for item in snapshot["platforms"])
    detail = service.get_run(created.run_id)
    assert detail.mode == "account_discovery"
    assert detail.account_selection == request.account_selection
    assert detail.published_from == request.account_selection.published_from
    assert detail.published_to == request.account_selection.published_to
    assert {scope.account.account_id for scope in detail.scopes} == {
        "red-1",
        "user-2",
        "dy-1",
        "123",
    }
    rows = service.list_runtime_runs(
        CollectionRuntimeListQuery(record_types=("tikhub_account_discovery",))
    )
    assert len(rows.items) == 1
    assert rows.items[0].record_type == "tikhub_account_discovery"
    assert "4 个账号" in rows.items[0].display_name
    capabilities = service.get_capabilities()
    assert all(
        item.account is not None and "account_discovery" in item.operations
        for item in capabilities.capabilities
    )


@pytest.mark.parametrize("platform", ["xiaohongshu", "douyin", "weibo", "bilibili", "kuaishou"])
@pytest.mark.parametrize("full_comments", [False, True])
def test_account_worker_ingests_unbranded_post_via_existing_owner(
    runtime, platform, full_comments, retry_comments=False
):  # type: ignore[no-untyped-def]
    """真实 PG/Worker/Raw/Mapper：账号作品不依赖品牌命中，仍必须匹配作者。"""
    config_id, _ = _seed_config_and_search_pack(runtime)
    fixture_name = (
        "image_detail.sanitized.json" if platform == "xiaohongshu" else "detail.sanitized.json"
    )
    detail = json.loads(
        (Path("tests/fixtures/providers/tikhub") / platform / fixture_name).read_text(
            encoding="utf-8"
        )
    )
    item = tikhub_runtime.extract_detail_items(platform, detail)[0]
    total = 530 if full_comments else 0
    if platform == "xiaohongshu":
        item["comments_count"] = total
    elif platform == "douyin":
        item["aweme_id"] = "100001"
        item["statistics"]["comment_count"] = total
        detail["data"]["aweme_detail"] = item
    elif platform == "weibo":
        item.update(id=100001, idstr="100001", mid="100001")
        item["user"].update(id=100002, idstr="100002")
        item["comments_count"] = total
    elif platform == "bilibili":
        item["stat"]["reply"] = total
    else:
        item["comment_count"] = total
    mapped = tikhub_runtime.map_content(
        platform=platform,
        raw=item,
        item_locator="fixture",
        context=tikhub_runtime.mapping_context(
            provider_request_id=str(uuid4()),
            provider_attempt_id=str(uuid4()),
            raw_artifact_id=uuid4(),
            operation="fixture",
            source_type="account",
            source_value="fixture",
            observed_at=beijing_now(),
        ),
    )
    assert mapped.author is not None and mapped.author.external_account_id
    account_id = mapped.author.external_account_id
    profile_response = None
    if platform == "xiaohongshu":
        id_type = "user_id"
        profile_response = {"data": {"user": {"user_id": account_id}}}
        posts = {"data": {"notes": [item], "has_more": False}}
        empty = None
    elif platform == "douyin":
        id_type = "sec_uid"
        account_id = mapped.author.alternate_ids["sec_uid"]
        posts = {"data": {"aweme_list": [item], "has_more": False, "max_cursor": 0}}
        empty = None
    elif platform == "weibo":
        id_type = "uid"
        posts = {"data": {"data": {"list": [item], "since_id": ""}}}
        empty = {"data": {"data": {"list": []}}}
    elif platform == "bilibili":
        id_type = "uid"
        posts = {"data": {"data": {"archives": [item]}}}
        empty = {"data": {"data": {"archives": []}}}
    else:
        id_type = "user_id"
        profile_response = {"data": {"userProfile": {"profile": {"user_id": account_id}}}}
        posts = {"data": {"photos": [item], "pcursor": "no_more"}}
        empty = None
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"a" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="account_discovery",
            account_selection={
                "kind": "accounts",
                "accounts": [
                    {"platform": platform, "account_id_type": id_type, "account_id": account_id}
                ],
                "published_from": "2024-01-01T00:00:00+08:00",
                "published_to": "2026-12-31T23:59:59+08:00",
            },
            platforms=({"platform": platform, "provider_config_id": config_id},),
            include_comments=full_comments,
            include_sub_comments=full_comments,
        ),
        request_id="account-worker-owner",
    )
    comment_bodies = (
        _full_comment_pages(platform, mapped.external_content_id) if full_comments else []
    )
    bodies = (
        ([profile_response] if profile_response is not None else [])
        + [posts, detail]
        + comment_bodies
        + ([empty] if empty is not None else [])
    )
    transport = FakeProviderTransport(
        tuple(ProviderTransportResponse(status_code=200, body=body) for body in bodies)
    )
    if retry_comments:
        prefix = ([profile_response] if profile_response is not None else []) + [posts, detail]
        transport = FakeProviderTransport(
            (
                *(ProviderTransportResponse(status_code=200, body=body) for body in prefix),
                ProviderTransportResponse(status_code=503, body={"error": "temporary"}),
                *(ProviderTransportResponse(status_code=200, body=body) for body in comment_bodies),
                *(
                    ProviderTransportResponse(status_code=200, body=body)
                    for body in ([empty] if empty is not None else [])
                ),
            )
        )
    worker = create_job_worker(
        runtime=runtime,
        worker_id="account-owner",
        lease_seconds=120,
        retry_delay_seconds=0,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _ref: SecretStr("fixture-secret"),
        ),
    )
    assert worker.run_once()
    if retry_comments:
        assert worker.run_once()
        assert not worker.run_once()
    run = service.get_run(created.run_id)
    assert run.status == "succeeded", run.model_dump()
    assert run.stats.content_count == 1
    assert run.scopes[0].posts_discovered == 1 and run.scopes[0].posts_admitted == 1
    assert transport.call_count == len(bodies) + int(retry_comments)
    if retry_comments:
        paths = [request.path for request in transport.seen_requests]
        assert paths.count(tikhub_runtime.build_detail_call(platform, mapped).path) == 1
        assert paths.count(
            next(
                request.path
                for request in transport.seen_requests
                if request.path.endswith(
                    (
                        "get_user_posted_notes",
                        "fetch_user_post_videos",
                        "fetch_user_posts",
                        "fetch_user_post_videos_v2",
                        "fetch_user_post_v2",
                    )
                )
            )
        ) == (2 if empty is not None else 1)
    with runtime.database.new_session() as session:
        stored = session.execute(select(contents_table)).mappings().one()
        assert stored["external_content_id"] == mapped.external_content_id
        assert stored["platform"] == platform
        if full_comments:
            assert session.scalar(select(func.count()).select_from(comments_table)) == 530
            assert run.stats.root_comment_count == 500
            assert run.stats.reply_count == 30
            coverage = session.execute(select(comment_coverage_observations_table)).mappings().all()
            assert any(
                row["coverage"] == "complete" and row["collected_count"] == 530 for row in coverage
            )


@pytest.mark.parametrize("platform", ["xiaohongshu", "douyin", "weibo", "bilibili", "kuaishou"])
def test_account_comment_retry_reuses_identity_posts_and_detail_raw(runtime, platform):  # type: ignore[no-untyped-def]
    """评论第一页 503 后由持久 Job 重试，不重复调用成功身份/作品/详情。"""
    test_account_worker_ingests_unbranded_post_via_existing_owner(
        runtime, platform, True, retry_comments=True
    )


def test_account_detail_failure_preserves_verified_post_and_other_account(runtime):  # type: ignore[no-untyped-def]
    """不可重试的详情错误不丢弃已核验的账号作品，也不阻塞其他账号。"""
    config_id, _ = _seed_config_and_search_pack(runtime)
    fixtures = {}
    for index in (1, 2):
        body = json.loads(
            Path(
                "tests/fixtures/providers/tikhub/xiaohongshu/image_detail.sanitized.json"
            ).read_text(encoding="utf-8")
        )
        item = tikhub_runtime.extract_detail_items("xiaohongshu", body)[0]
        item.update(id=f"account-note-{index}", comments_count=0)
        item["user"]["userid"] = f"account-user-{index}"
        fixtures[f"account-user-{index}"] = body

    class Transport:
        call_count = 0

        def send(self, request):  # type: ignore[no-untyped-def]
            self.call_count += 1
            if request.path.endswith("get_user_info"):
                identity = request.params["user_id"]
                assert identity in fixtures
                return ProviderTransportResponse(
                    status_code=200, body={"data": {"user": {"user_id": identity}}}
                )
            if request.path.endswith("get_user_posted_notes"):
                body = fixtures[request.params["user_id"]]
                return ProviderTransportResponse(
                    status_code=200,
                    body={
                        "data": {
                            "notes": list(tikhub_runtime.extract_detail_items("xiaohongshu", body)),
                            "has_more": False,
                        }
                    },
                )
            assert request.path.endswith("get_image_note_detail")
            if request.params["note_id"] == "account-note-2":
                return ProviderTransportResponse(status_code=400, body={"error": "unavailable"})
            assert request.params["note_id"] == "account-note-1"
            return ProviderTransportResponse(status_code=200, body=fixtures["account-user-1"])

    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"a" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="account_discovery",
            platforms=({"platform": "xiaohongshu", "provider_config_id": config_id},),
            account_selection={
                "kind": "accounts",
                "accounts": [
                    {
                        "platform": "xiaohongshu",
                        "account_id_type": "user_id",
                        "account_id": f"account-user-{index}",
                    }
                    for index in (1, 2)
                ],
                "published_from": "2024-01-01T00:00:00+08:00",
                "published_to": "2026-12-31T23:59:59+08:00",
            },
            include_comments=False,
            include_sub_comments=False,
        ),
        request_id="account-detail-failure-isolation",
    )
    transport = Transport()
    worker = create_job_worker(
        runtime=runtime,
        worker_id="account-isolation",
        lease_seconds=120,
        retry_delay_seconds=0,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _ref: SecretStr("fixture-secret"),
        ),
    )
    assert worker.run_once()
    run = service.get_run(created.run_id)
    assert run.status == "partial_success"
    assert run.stats.content_count == 2
    assert {scope.status for scope in run.scopes} == {"succeeded", "partial_success"}
    assert transport.call_count == 6
    with runtime.database.new_session() as session:
        assert set(session.scalars(select(contents_table.c.external_content_id))) == {
            "account-note-1",
            "account-note-2",
        }


def _xiaohongshu_account_run(runtime, config_id, identities, *, comments=True):
    """建立复用正式请求契约的多账号回归任务。"""
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"a" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="account_discovery",
            platforms=({"platform": "xiaohongshu", "provider_config_id": config_id},),
            account_selection={
                "kind": "accounts",
                "accounts": [
                    {
                        "platform": "xiaohongshu",
                        "account_id_type": "user_id",
                        "account_id": identity,
                    }
                    for identity in identities
                ],
                "published_from": "2024-01-01T00:00:00+08:00",
                "published_to": "2026-12-31T23:59:59+08:00",
            },
            include_comments=comments,
            include_sub_comments=comments,
        ),
        request_id="account-checkpoint-regression",
    )
    return service, created


def _account_worker(runtime, transport):
    return create_job_worker(
        runtime=runtime,
        worker_id="account-checkpoint",
        lease_seconds=120,
        retry_delay_seconds=0,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _ref: SecretStr("fixture-secret"),
        ),
    )


def _xiaohongshu_detail(identity, note_id, comments=0):
    body = json.loads(
        Path("tests/fixtures/providers/tikhub/xiaohongshu/image_detail.sanitized.json").read_text(
            encoding="utf-8"
        )
    )
    item = tikhub_runtime.extract_detail_items("xiaohongshu", body)[0]
    item.update(id=note_id, comments_count=comments)
    item["user"]["userid"] = identity
    return body


@pytest.mark.parametrize("retry_second_page", [False, True])
def test_account_post_checkpoint_survives_comments_on_later_pages(runtime, retry_second_page):
    """三页作品穿插评论/回复，第二页失败恢复仍保留账号身份和作品游标。"""
    config_id, _ = _seed_config_and_search_pack(runtime)
    details = {
        f"multi-note-{page}": _xiaohongshu_detail("multi-user", f"multi-note-{page}", 2)
        for page in range(1, 4)
    }
    template = tikhub_runtime.extract_comment_items(
        "xiaohongshu",
        json.loads(
            Path(
                "tests/fixtures/providers/tikhub/xiaohongshu/comments_page1.sanitized.json"
            ).read_text(encoding="utf-8")
        ),
    )[0]

    class Transport:
        def __init__(self):
            self.seen = []
            self.failed = False

        def send(self, request):
            self.seen.append((request.path, dict(request.params)))
            if request.path.endswith("get_user_info"):
                body = {"data": {"user": {"user_id": "multi-user"}}}
            elif request.path.endswith("get_user_posted_notes"):
                page = int(request.params.get("cursor") or 0) + 1
                item = tikhub_runtime.extract_detail_items(
                    "xiaohongshu", details[f"multi-note-{page}"]
                )[0]
                body = {"data": {"notes": [item], "cursor": str(page), "has_more": page < 3}}
            elif request.path.endswith("get_image_note_detail"):
                body = details[request.params["note_id"]]
            else:
                note_id = request.params["note_id"]
                page = int(note_id.rsplit("-", 1)[1])
                is_reply = request.path.endswith("get_note_sub_comments")
                if retry_second_page and page == 2 and not is_reply and not self.failed:
                    self.failed = True
                    return ProviderTransportResponse(status_code=503, body={"error": "temporary"})
                root_id = 9000 + page
                row = _comment_row(
                    "xiaohongshu",
                    template,
                    note_id,
                    root_id + (100 if is_reply else 0),
                    root=root_id if is_reply else None,
                    replies=0 if is_reply else 1,
                )
                body = _comment_envelope("xiaohongshu", [row], 0, more=False, replies=is_reply)
            return ProviderTransportResponse(status_code=200, body=body)

    service, created = _xiaohongshu_account_run(runtime, config_id, ("multi-user",))
    transport = Transport()
    worker = _account_worker(runtime, transport)
    assert worker.run_once()
    if retry_second_page:
        assert worker.run_once()
    assert not worker.run_once()
    run = service.get_run(created.run_id)
    assert run.status == "succeeded", run.model_dump()
    assert run.stats.content_count == 3
    assert run.stats.root_comment_count == 3 and run.stats.reply_count == 3
    with runtime.database.new_session() as session:
        scope = (
            session.execute(
                select(collection_scopes_table).where(
                    collection_scopes_table.c.run_id == created.run_id
                )
            )
            .mappings()
            .one()
        )
        assert scope["pagination_state"]["_account_identity"]["stable_id"] == "multi-user"
        assert scope["pagination_state"]["cursor"] == "2"
    assert sum(path.endswith("get_user_info") for path, _ in transport.seen) == 1
    assert sum(path.endswith("get_user_posted_notes") for path, _ in transport.seen) == 3
    assert sum(path.endswith("get_image_note_detail") for path, _ in transport.seen) == 3


def test_persistent_retryable_account_failure_does_not_block_healthy_account(runtime):
    """前一个账号连续 503 耗尽两次尝试，后一个账号仍成功且不重复发送。"""
    config_id, _ = _seed_config_and_search_pack(runtime)
    detail = _xiaohongshu_detail("z-healthy", "healthy-note")
    item = tikhub_runtime.extract_detail_items("xiaohongshu", detail)[0]

    class Transport:
        def __init__(self):
            self.seen = []

        def send(self, request):
            self.seen.append((request.path, dict(request.params)))
            if request.path.endswith("get_user_info"):
                user_id = request.params["user_id"]
                if user_id == "a-failing":
                    return ProviderTransportResponse(status_code=503, body={"error": "temporary"})
                body = {"data": {"user": {"user_id": user_id}}}
            elif request.path.endswith("get_user_posted_notes"):
                assert request.params["user_id"] == "z-healthy"
                body = {"data": {"notes": [item], "has_more": False}}
            else:
                assert request.params["note_id"] == "healthy-note"
                body = detail
            return ProviderTransportResponse(status_code=200, body=body)

    service, created = _xiaohongshu_account_run(
        runtime, config_id, ("a-failing", "z-healthy"), comments=False
    )
    transport = Transport()
    worker = _account_worker(runtime, transport)
    assert worker.run_once()
    with runtime.database.new_session() as session:
        assert session.scalar(select(func.count()).select_from(contents_table)) == 1
    assert worker.run_once()
    assert not worker.run_once()
    run = service.get_run(created.run_id)
    assert run.status == "partial_success", run.model_dump()
    assert run.stats.content_count == 1
    assert {scope.status for scope in run.scopes} == {"failed", "succeeded"}
    assert next(scope for scope in run.scopes if scope.status == "failed").stop_reason == "http_503"
    assert len(transport.seen) == 5


def _full_comment_pages(platform: str, content_id: str) -> list[dict]:
    """在真实响应形状中生成五页根评论和两页回复，检验正式 500/30 接线。"""
    fixture = json.loads(
        (
            Path("tests/fixtures/providers/tikhub") / platform / "comments_page1.sanitized.json"
        ).read_text(encoding="utf-8")
    )
    template = tikhub_runtime.extract_comment_items(platform, fixture)[0]
    pages = []
    for page in range(5):
        rows = [
            _comment_row(
                platform,
                template,
                content_id,
                100000 + page * 100 + index,
                root=None,
                replies=30 if page == 0 and index == 0 else 0,
            )
            for index in range(100)
        ]
        pages.append(_comment_envelope(platform, rows, page, more=page < 4, replies=False))
    for page in range(2):
        rows = [
            _comment_row(
                platform, template, content_id, 200000 + page * 15 + index, root=100000, replies=0
            )
            for index in range(15)
        ]
        pages.append(_comment_envelope(platform, rows, page, more=page == 0, replies=True))
    # 正式执行器在每页根评论后处理该页回复，并非最后集中处理全部回复。
    return [pages[0], *pages[5:], *pages[1:5]]


@pytest.mark.parametrize("failure_stage", ["identity", "detail"])
def test_user_retry_only_reopens_failed_account_and_reuses_healthy_raw(runtime, failure_stage):
    """显式重试保留同一 Job/Run，成功账号不重跑，旧失败 Attempt 不被覆盖。"""
    config_id, _ = _seed_config_and_search_pack(runtime)
    details = {
        identity: _xiaohongshu_detail(identity, f"note-{identity}")
        for identity in ("a-failing", "z-healthy")
    }

    class Transport:
        def __init__(self):
            self.failed = True
            self.seen = []

        def send(self, request):
            self.seen.append((request.path, dict(request.params)))
            if request.path.endswith("get_user_info"):
                identity = request.params["user_id"]
                if identity == "a-failing" and self.failed and failure_stage == "identity":
                    return ProviderTransportResponse(status_code=400, body={"error": "unavailable"})
                body = {"data": {"user": {"user_id": identity}}}
            elif request.path.endswith("get_user_posted_notes"):
                body = {
                    "data": {
                        "notes": list(
                            tikhub_runtime.extract_detail_items(
                                "xiaohongshu", details[request.params["user_id"]]
                            )
                        ),
                        "has_more": False,
                    }
                }
            else:
                if (
                    request.params["note_id"] == "note-a-failing"
                    and self.failed
                    and failure_stage == "detail"
                ):
                    return ProviderTransportResponse(status_code=400, body={"error": "unavailable"})
                body = details[request.params["note_id"].removeprefix("note-")]
            return ProviderTransportResponse(status_code=200, body=body)

    service, created = _xiaohongshu_account_run(
        runtime, config_id, ("a-failing", "z-healthy"), comments=False
    )
    transport = Transport()
    worker = _account_worker(runtime, transport)
    assert worker.run_once()
    assert service.get_run(created.run_id).status == "partial_success"
    assert len(transport.seen) == (4 if failure_stage == "identity" else 6)
    restarted = service.retry_run(created.run_id)
    assert restarted.run_id == created.run_id and restarted.job_id == created.job_id
    assert restarted.status == "queued"
    transport.failed = False
    assert worker.run_once()
    assert not worker.run_once()
    finished = service.get_run(created.run_id)
    assert finished.status == "succeeded", (
        [(scope.status, scope.stop_reason, scope.stats.model_dump()) for scope in finished.scopes],
        transport.seen,
    )
    assert finished.stats.content_count == 2
    assert len(transport.seen) == 7
    assert sum(params.get("user_id") == "z-healthy" for _, params in transport.seen) == 2
    if failure_stage == "detail":
        assert sum(params.get("user_id") == "a-failing" for _, params in transport.seen) == 2
        assert sum(params.get("note_id") == "note-a-failing" for _, params in transport.seen) == 2
    with runtime.database.new_session() as session:
        assert session.scalar(select(func.count()).select_from(contents_table)) == 2
    assert finished.attempt == 2


@pytest.mark.parametrize("running", [False, True])
def test_account_cancel_uses_job_owner_and_settles_run_scopes(runtime, running):
    """排队和发送过程中取消均通过共享 Job Owner 收敛，无后续付费请求。"""
    config_id, _ = _seed_config_and_search_pack(runtime)
    service, created = _xiaohongshu_account_run(
        runtime, config_id, ("cancel-user",), comments=False
    )

    class Transport:
        call_count = 0

        def send(self, request):
            self.call_count += 1
            service.cancel_run(created.run_id)
            return ProviderTransportResponse(
                status_code=200, body={"data": {"user": {"user_id": "cancel-user"}}}
            )

    transport = Transport()
    worker = _account_worker(runtime, transport)
    if running:
        assert worker.run_once()
    else:
        service.cancel_run(created.run_id)
        assert not worker.run_once()
    run = service.get_run(created.run_id)
    assert run.status == "cancelled" and run.stage == "cancelled"
    assert all(scope.status == "cancelled" for scope in run.scopes)
    assert transport.call_count == int(running)


def test_account_cancel_after_run_commit_converges_to_job_terminal(runtime, monkeypatch):
    """Run 已提交但 Job 尚未结算时，取消仍须在 Job 终态事务统一裁决。"""
    from aima_ugc.adapters.persistence.postgres.collection_run_execution import (
        PostgresCollectionRunExecutionGateway,
    )
    from aima_ugc.platform.jobs.tables import jobs_table

    config_id, _ = _seed_config_and_search_pack(runtime)
    service, created = _xiaohongshu_account_run(
        runtime, config_id, ("late-cancel",), comments=False
    )
    detail = _xiaohongshu_detail("late-cancel", "note-late-cancel")
    transport = FakeProviderTransport(
        outcomes=(
            ProviderTransportResponse(
                status_code=200, body={"data": {"user": {"user_id": "late-cancel"}}}
            ),
            ProviderTransportResponse(
                status_code=200,
                body={
                    "data": {
                        "notes": list(tikhub_runtime.extract_detail_items("xiaohongshu", detail)),
                        "has_more": False,
                    }
                },
            ),
            ProviderTransportResponse(status_code=200, body=detail),
        )
    )
    original = PostgresCollectionRunExecutionGateway.finish_run

    def finish_then_cancel(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        service.cancel_run(created.run_id)
        return result

    monkeypatch.setattr(PostgresCollectionRunExecutionGateway, "finish_run", finish_then_cancel)
    assert _account_worker(runtime, transport).run_once()
    completed = service.get_run(created.run_id)
    assert completed.status == "cancelled" and completed.stage == "cancelled"
    assert completed.stats.content_count == 1
    assert completed.scopes[0].status == "succeeded"
    with runtime.database.new_session() as session:
        assert (
            session.scalar(
                select(collection_runs_table.c.status).where(
                    collection_runs_table.c.id == created.run_id
                )
            )
            == "cancelled"
        )
        assert (
            session.scalar(select(jobs_table.c.status).where(jobs_table.c.id == created.job_id))
            == "cancelled"
        )
        assert session.scalar(select(func.count()).select_from(contents_table)) == 1


def test_manual_retry_detail_conflict_keeps_page_canonical_and_continues_next_post(runtime):
    """详情恢复后的准入变化不改变作品 Raw 的 Canonical 集合，也不截断其他作品。"""
    config_id, _ = _seed_config_and_search_pack(runtime)
    identity = "recovery-user"
    details = {note: _xiaohongshu_detail(identity, note) for note in ("note-conflict", "note-next")}
    service, created = _xiaohongshu_account_run(runtime, config_id, (identity,), comments=False)

    class Transport:
        recovered = False

        def __init__(self):
            self.seen = []

        def send(self, request):
            self.seen.append((request.path, dict(request.params)))
            if request.path.endswith("get_user_info"):
                body = {"data": {"user": {"user_id": identity}}}
            elif request.path.endswith("get_user_posted_notes"):
                body = {"data": {"notes": [
                    tikhub_runtime.extract_detail_items("xiaohongshu", detail)[0]
                    for detail in details.values()
                ], "has_more": False}}
            elif not self.recovered:
                return ProviderTransportResponse(status_code=400, body={"error": "unavailable"})
            else:
                body = deepcopy(details[request.params["note_id"]])
                if request.params["note_id"] == "note-conflict":
                    body["data"]["data"][0]["note_list"][0]["user"]["userid"] = "foreign-user"
            return ProviderTransportResponse(status_code=200, body=body)

    transport = Transport()
    worker = _account_worker(runtime, transport)
    assert worker.run_once()
    assert service.get_run(created.run_id).status == "partial_success"
    service.retry_run(created.run_id)
    transport.recovered = True
    assert worker.run_once()
    run = service.get_run(created.run_id)
    assert run.status == "partial_success"
    assert run.scopes[0].status == "partial_success"
    assert run.scopes[0].stop_reason == "provider_exhausted"
    assert run.stats.content_count == 2
    assert len(transport.seen) == 6
    assert sum(params.get("note_id") == "note-next" for _, params in transport.seen) == 2
    assert sum(path.endswith("get_user_posted_notes") for path, _ in transport.seen) == 1
    with runtime.database.new_session() as session:
        assert session.scalar(select(func.count()).select_from(contents_table)) == 2


def _comment_row(
    platform: str, template: dict, content_id: str, identity: int, *, root: int | None, replies: int
) -> dict:
    row = deepcopy(template)
    if platform == "xiaohongshu":
        row.update(id=str(identity), note_id=content_id, sub_comment_count=replies, sub_comments=[])
        if root is not None:
            row["target_comment"] = {"id": str(root)}
    elif platform == "douyin":
        row.update(
            cid=str(identity),
            aweme_id=content_id,
            reply_comment_total=replies,
            reply_id=str(root or 0),
            reply_to_reply_id="0",
        )
    elif platform == "weibo":
        row.update(
            id=identity,
            idstr=str(identity),
            mid=str(identity),
            rootid=root or identity,
            rootidstr=str(root or identity),
            rid=str(root or 0),
            total_number=replies,
        )
    elif platform == "bilibili":
        row.update(
            rpid=identity,
            rpid_str=str(identity),
            oid=content_id,
            root=root or 0,
            root_str=str(root or 0),
            parent=root or 0,
            parent_str=str(root or 0),
            rcount=replies,
            replies=[],
        )
    else:
        row.update(
            comment_id=identity, photo_id=content_id, subCommentCount=replies, reply_to=root or 0
        )
    return row


def _comment_envelope(
    platform: str, rows: list[dict], page: int, *, more: bool, replies: bool
) -> dict:
    if platform == "xiaohongshu":
        return {"data": {"data": {"comments": rows, "cursor": str(page + 1), "has_more": more}}}
    if platform == "douyin":
        return {
            "data": {
                "comments": rows,
                "cursor": (page + 1) * 100,
                "has_more": int(more),
                "total": 30 if replies else 530,
                "status_code": 0,
            }
        }
    if platform == "weibo":
        if replies:
            return {"data": {"data": rows, "max_id": str(page + 1) if more else 0}}
        return {
            "data": {
                "items": [{"data": row} for row in rows],
                **({"moreInfo": {"params": {"max_id": str(page + 1)}}} if more else {}),
            }
        }
    if platform == "bilibili":
        data = {
            "replies": rows,
            "cursor": {
                "next": page + 1,
                "pagination_reply": {"next_offset": page + 1},
                "is_end": not more,
            },
            "page": {"count": 30 if replies else 530, "num": page + 1, "size": len(rows)},
        }
        if replies:
            data["root"] = {"rpid": 100000, "replies": rows}
        return {"code": 200, "data": {"data": data}}
    return {
        "data": {
            "subComments" if replies else "rootComments": rows,
            "commentCount": 530,
            "pcursor": str(page + 1) if more else "no_more",
            "result": 1,
        }
    }
