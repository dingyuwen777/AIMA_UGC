"""一次性 TikHub 生产代码/测试最终化；执行后删除。"""
from pathlib import Path
from textwrap import dedent


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: replacement source count != 1: {old[:80]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


def replace_required(path: str, pairs: tuple[tuple[str, str], ...]) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"{path}: missing {old!r}")
        text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")


replace_once(
    "backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py",
    '''        ProviderOperationCapabilityV1(\n            business_operation="comments",\n            provider_operations=("fetch_video_comments",),\n            comment_sort_modes=("latest", "hot"),\n            supports_reply_count=True,\n            supports_sub_comments=True,\n            supports_incremental_comment_sort=False,\n            provider_page_size_policy="provider_default",\n        ),''',
    '''        ProviderOperationCapabilityV1(\n            business_operation="comments",\n            provider_operations=("fetch_video_comments",),\n            comment_sort_modes=("latest", "hot"),\n            supports_reply_count=True,\n            supports_sub_comments=True,\n            supports_incremental_comment_sort=True,\n            provider_page_size_policy="provider_default",\n        ),''',
)

replace_once(
    "tests/unit/collection/test_tikhub_real_capabilities.py",
    '''    # XHS App V2 comments 固定 latest_v2，且官方说明为时间倒序/最新优先；\n    # 其余平台当前仍缺少同等级“可按历史 comment_id 安全截断”的证据。\n    assert _operation(XHS_TIKHUB_CAPABILITY, "comments").supports_incremental_comment_sort is True\n    for capability in (\n        DOUYIN_TIKHUB_CAPABILITY,\n        WEIBO_TIKHUB_CAPABILITY,\n        BILIBILI_TIKHUB_CAPABILITY,\n        KUAISHOU_TIKHUB_CAPABILITY,\n    ):\n        assert _operation(capability, "comments").supports_incremental_comment_sort is False''',
    '''    # XHS latest_v2 与 B站 mode=2/next_offset=0 都有当前真实“最新优先”证据；\n    # 抖音缺少最新评论排序，微博/快手真实页顺序不满足安全历史边界。\n    assert _operation(XHS_TIKHUB_CAPABILITY, "comments").supports_incremental_comment_sort is True\n    assert (\n        _operation(BILIBILI_TIKHUB_CAPABILITY, "comments").supports_incremental_comment_sort\n        is True\n    )\n    for capability in (\n        DOUYIN_TIKHUB_CAPABILITY,\n        WEIBO_TIKHUB_CAPABILITY,\n        KUAISHOU_TIKHUB_CAPABILITY,\n    ):\n        assert _operation(capability, "comments").supports_incremental_comment_sort is False''',
)

p = Path("tests/unit/collection/test_stage7_decision.py")
text = p.read_text(encoding="utf-8")
old_import = "from aima_ugc.adapters.providers.tikhub.capabilities import XHS_TIKHUB_CAPABILITY"
if old_import not in text:
    raise SystemExit("decision import missing")
text = text.replace(
    old_import,
    "from aima_ugc.adapters.providers.tikhub.capabilities import (\n"
    "    BILIBILI_TIKHUB_CAPABILITY,\n    XHS_TIKHUB_CAPABILITY,\n)",
)
marker = "\ndef test_comment_count_decrease_never_guesses_specific_deletion() -> None:\n"
if marker not in text:
    raise SystemExit("decision marker missing")
test = dedent('''

    def test_bilibili_comment_count_increase_uses_verified_incremental_sort() -> None:
        request = _request(current_comment_count=80, previous_comment_count=35, existing=True)
        request = request.model_copy(update={"capability": BILIBILI_TIKHUB_CAPABILITY})
        decision = CollectionDecisionService().decide(request)
        assert decision.comment_action == "fetch_incremental"
        assert decision.comment_reason == "comment_count_increased_incremental"
    ''')
p.write_text(text.replace(marker, test + marker), encoding="utf-8")

replace_required(
    "backend/src/aima_ugc/adapters/providers/tikhub_test/excel.py",
    (("人工审阅 XLSX", "原始数据 XLSX"), ("ReviewContent", "RawDataContent"),
     ("ReviewCommentRow", "RawDataCommentRow"), ("ReviewBlock", "RawDataBlock"),
     ("write_review_workbook", "write_raw_data_workbook"),
     ("纵向区块人工审阅 Workbook", "纵向区块原始数据 Workbook")),
)
replace_required(
    "backend/src/aima_ugc/adapters/providers/tikhub_test/runner.py",
    (("ReviewContent", "RawDataContent"), ("ReviewCommentRow", "RawDataCommentRow"),
     ("ReviewBlock", "RawDataBlock"), ("write_review_workbook", "write_raw_data_workbook"),
     ("review_dir", "raw_data_dir"), ("_review_content", "_raw_data_content"),
     ("_review_comment", "_raw_data_comment"), ("_review.xlsx", "_raw_data.xlsx"),
     ("_manifest", "_run_summary")),
)
replace_required(
    "backend/src/aima_ugc/adapters/providers/tikhub_test/core.py",
    (("review_dir", "raw_data_dir"), ('run_dir / "review"', 'run_dir / "raw_data"')),
)
replace_required(
    "tests/unit/collection/test_tikhub_test_debug.py",
    (("ReviewContent", "RawDataContent"), ("ReviewCommentRow", "RawDataCommentRow"),
     ("ReviewBlock", "RawDataBlock"), ("write_review_workbook", "write_raw_data_workbook"),
     ("test_review_workbook_uses_approved_content_comment_layout", "test_raw_data_workbook_uses_approved_content_comment_layout")),
)
replace_required(
    "backend/src/aima_ugc/adapters/providers/tikhub_test/README.md",
    (("xhs_review.xlsx", "xhs_raw_data.xlsx"), ("review/", "raw_data/")),
)
