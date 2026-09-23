from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch

from aima_ugc.bootstrap.representative_report_pipeline import (
    _is_usable_screenshot,
    _OptionalScreenshotSession,
    _representative_comment,
)
from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingLLMResponse,
)
from aima_ugc.modules.analysis.representative_advice import (
    RepresentativeAdviceInput,
    RepresentativeAdviceService,
)
from aima_ugc.modules.analysis.representative_selection import LabeledContent
from aima_ugc.platform.reporting import (
    RepresentativeReportRow,
    build_representative_section,
    convert_markdown_to_docx,
    format_representative_labels,
    normalize_representative_content_url,
)
from PIL import Image


class _FakeAdviceLLM:
    provider_name = "fake"
    model_name = "fake-model"

    def complete(self, request: object) -> ContentLabelingLLMResponse:
        items = request.items  # type: ignore[attr-defined]
        return ContentLabelingLLMResponse(
            raw_text=(
                '{"items":['
                + ",".join(
                    f'{{"item_no":{item.item_no},"action_advice":"建议跟进{item.item_no}"}}'
                    for item in items
                )
                + "]}"
            )
        )


class _EnglishThenChineseAdviceLLM:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: object) -> ContentLabelingLLMResponse:
        self.calls += 1
        items = request.items  # type: ignore[attr-defined]
        advice = (
            "请核查相关问题并及时跟进处理。"
            if self.calls > 1
            else "Please follow up with the user and improve the service."
        )
        return ContentLabelingLLMResponse(
            raw_text=(
                '{"items":['
                + ",".join(
                    f'{{"item_no":{item.item_no},"action_advice":"{advice}"}}' for item in items
                )
                + "]}"
            )
        )


class _InvalidThenValidAdviceLLM:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self) -> None:
        self.calls = 0
        self.request_kinds: list[str] = []

    def complete(self, request: object) -> ContentLabelingLLMResponse:
        self.calls += 1
        self.request_kinds.append(request.request_kind)  # type: ignore[attr-defined]
        if self.calls == 1:
            return ContentLabelingLLMResponse(raw_text="{}")
        items = request.items  # type: ignore[attr-defined]
        return ContentLabelingLLMResponse(
            raw_text=(
                '{"items":['
                + ",".join(
                    f'{{"item_no":{item.item_no},"action_advice":"修复后建议{item.item_no}"}}'
                    for item in items
                )
                + "]}"
            )
        )


class _AlwaysInvalidAdviceLLM:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: object) -> ContentLabelingLLMResponse:
        self.calls += 1
        return ContentLabelingLLMResponse(raw_text="{}")


def test_action_advice_service_keeps_item_identity() -> None:
    result = RepresentativeAdviceService(llm=_FakeAdviceLLM()).run(
        (
            RepresentativeAdviceInput(
                item_no=1,
                platform="抖音",
                sentiment="负面",
                primary_label="售后服务",
                secondary_label="维修处理效率与质量",
                comment_text="维修等待时间较长",
            ),
            RepresentativeAdviceInput(
                item_no=2,
                platform="小红书",
                sentiment="正面",
                primary_label="品牌评价",
                secondary_label="口碑与信任",
                comment_text="整体体验不错",
            ),
        )
    )

    assert result == {1: "建议跟进1", 2: "建议跟进2"}


def test_action_advice_service_rewrites_english_to_chinese() -> None:
    llm = _EnglishThenChineseAdviceLLM()
    result = RepresentativeAdviceService(llm=llm).run(
        (
            RepresentativeAdviceInput(
                item_no=1,
                platform="抖音",
                sentiment="负面",
                primary_label="售后服务",
                secondary_label="客服与服务态度",
                comment_text="服务态度有待改善",
            ),
        )
    )

    assert result == {1: "请核查相关问题并及时跟进处理。"}
    assert llm.calls == 2


def test_action_advice_service_repairs_invalid_primary_response() -> None:
    llm = _InvalidThenValidAdviceLLM()
    result = RepresentativeAdviceService(llm=llm).run(
        (
            RepresentativeAdviceInput(
                item_no=1,
                platform="抖音",
                sentiment="负面",
                primary_label="售后服务",
                secondary_label="客服与服务态度",
                comment_text="服务态度有待改善",
            ),
        )
    )

    assert result == {1: "修复后建议1"}
    assert llm.calls == 2
    assert llm.request_kinds == ["primary", "repair"]


def test_action_advice_service_falls_back_when_both_responses_are_invalid() -> None:
    llm = _AlwaysInvalidAdviceLLM()
    result = RepresentativeAdviceService(llm=llm).run(
        (
            RepresentativeAdviceInput(
                item_no=1,
                platform="抖音",
                sentiment="负面",
                primary_label="售后服务",
                secondary_label="客服与服务态度",
                comment_text="服务态度有待改善",
            ),
            RepresentativeAdviceInput(
                item_no=2,
                platform="小红书",
                sentiment="正面",
                primary_label="品牌评价",
                secondary_label="口碑与信任",
                comment_text="整体体验不错",
            ),
        )
    )

    assert result == {
        1: "围绕售后服务、客服与服务态度核查具体原因，及时联系用户并跟进处理结果。",
        2: "围绕品牌评价、口碑与信任总结用户认可点，优化相关服务并持续收集反馈。",
    }
    assert llm.calls == 2


def test_representative_section_contains_four_groups_and_blank_progress(tmp_path: Path) -> None:
    screenshot = tmp_path / "shot.png"
    Image.new("RGB", (80, 60), "white").save(screenshot)
    root = tmp_path / "report"
    asset = root / "assets" / "representatives" / "shot.png"
    asset.parent.mkdir(parents=True)
    screenshot.replace(asset)
    markdown = build_representative_section(
        (
            RepresentativeReportRow(
                platform="小红书",
                sentiment="负面",
                content_id="xiaohongshu-1",
                content_url="https://example.com/a?x=1",
                link_text="爱玛售后服务不错",
                comment_text="评论内容",
                primary_label="售后服务",
                secondary_label="客服与服务态度",
                action_advice="建议回访并核查服务流程",
                screenshot_path=asset,
            ),
        ),
        report_root=root,
    )

    assert markdown.startswith("## 6. 代表性评论与关联页面")
    assert markdown.count("### 6.") == 4
    assert "[爱玛售后服务不错](https://example.com/a?x=1)" in markdown
    assert "![截图](assets/representatives/shot.png)" in markdown
    assert "建议回访并核查服务流程" in markdown
    # 第 7 列是明确的空字符串，不使用“待处理”等默认状态。
    assert "| 建议回访并核查服务流程 |  |" in markdown


def test_representative_section_deduplicates_labels_without_html_breaks() -> None:
    markdown = build_representative_section(
        (
            RepresentativeReportRow(
                platform="抖音",
                sentiment="正面",
                content_id="douyin-1",
                content_url="https://example.com/post",
                comment_text="评论内容" * 40,
                primary_label="售后服务\n售后服务<br>品牌评价",
                secondary_label="客服与服务态度\n客服与服务态度；维修处理效率与质量",
                action_advice="建议跟进",
            ),
        )
    )

    assert "售后服务、品牌评价" in markdown
    assert "客服与服务态度、维修处理效率与质量" in markdown
    assert "评论内容评论内容评论内容" not in markdown
    assert "评论内容" * 40 not in markdown
    assert "<br>" not in markdown


def test_representative_labels_split_feishu_multi_select_values_and_deduplicate() -> None:
    assert (
        format_representative_labels("骑行性能、骑行性能，售后服务<br>售后服务")
        == "骑行性能、售后服务"
    )
    assert format_representative_labels("骑行性能骑行性能") == "骑行性能"
    assert format_representative_labels("舒适性舒适性、品牌评价") == "舒适性、品牌评价"
    assert format_representative_labels("电池、续航与充电") == "电池、续航与充电"


def test_xiaohongshu_legacy_discovery_url_is_normalized() -> None:
    assert (
        normalize_representative_content_url(
            "小红书",
            "https://www.xiaohongshu.com/discovery/item/abc123?x=1",
        )
        == "https://www.xiaohongshu.com/explore/abc123?x=1"
    )


def test_missing_comment_keeps_report_comment_cell_blank() -> None:
    content = LabeledContent(
        row_number=2,
        platform="抖音",
        content_id="douyin-1",
        title="标题",
        text="正文内容",
        author="用户",
        published_at="",
        content_url="https://example.com/post",
        voice_type="真实用户发声",
        sentiment_label="正面",
    )

    assert _representative_comment(content, {}) == ""


def test_douyin_screenshot_uses_fixed_16_9_viewport(tmp_path: Path) -> None:
    class _FakePage:
        def __init__(self) -> None:
            self.goto_url = ""
            self.wait_ms = 0
            self.scroll_script = ""
            self.full_page = True

        def goto(self, url: str, **_: object) -> None:
            self.goto_url = url

        def wait_for_timeout(self, milliseconds: int) -> None:
            self.wait_ms = milliseconds

        def evaluate(self, script: str) -> bool | None:
            if script == "window.scrollTo(0, 0)":
                self.scroll_script = script
                return None
            return False

        def screenshot(
            self,
            *,
            path: str,
            full_page: bool,
            clip: dict[str, int],
        ) -> None:
            self.full_page = full_page
            self.clip = clip
            Image.new("RGB", (1280, 755), "white").save(path)

    page = _FakePage()
    session = _OptionalScreenshotSession([], target_dir=tmp_path)
    session._page = page  # type: ignore[assignment]
    row = RepresentativeReportRow(
        platform="抖音",
        sentiment="正面",
        content_id="douyin-1",
        content_url="https://example.com/post",
        comment_text="",
        primary_label="品牌评价",
        secondary_label="口碑与信任",
        action_advice="建议持续关注",
    )

    screenshot = session.fetch(row)

    assert screenshot == tmp_path / "screenshots" / "抖音_douyin-1.png"
    assert page.goto_url == row.content_url
    assert page.wait_ms == _OptionalScreenshotSession._PAGE_RENDER_WAIT_MS
    assert page.scroll_script == "window.scrollTo(0, 0)"
    assert page.full_page is False
    assert page.clip == {"x": 160, "y": 55, "width": 1280, "height": 755}
    assert _OptionalScreenshotSession._VIEWPORT == {"width": 1440, "height": 810}

    xiaohongshu_row = RepresentativeReportRow(
        platform="小红书",
        sentiment="正面",
        content_id="xiaohongshu-1",
        content_url="https://example.com/xiaohongshu",
        comment_text="",
        primary_label="品牌评价",
        secondary_label="口碑与信任",
        action_advice="建议持续关注",
    )
    assert session.fetch(xiaohongshu_row) is None


def test_douyin_screenshot_skips_login_overlay(tmp_path: Path) -> None:
    class _LoginPage:
        def goto(self, url: str, **_: object) -> None:
            del url

        def wait_for_timeout(self, milliseconds: int) -> None:
            del milliseconds

        def evaluate(self, script: str) -> bool:
            del script
            return True

        def screenshot(self, **_: object) -> None:
            raise AssertionError("登录弹窗页面不应写入截图")

    warnings: list[str] = []
    session = _OptionalScreenshotSession(warnings, target_dir=tmp_path)
    session._page = _LoginPage()  # type: ignore[assignment]
    row = RepresentativeReportRow(
        platform="抖音",
        sentiment="负面",
        content_id="douyin-login",
        content_url="https://www.douyin.com/video/1",
        comment_text="",
        primary_label="品牌评价",
        secondary_label="口碑与信任",
        action_advice="建议跟进",
    )

    assert session.fetch(row) is None
    assert not (tmp_path / "screenshots" / "抖音_douyin-login.png").exists()
    assert any("无法启用登录态" in warning for warning in warnings)


def test_douyin_screenshot_quality_rejects_black_loading_placeholder(tmp_path: Path) -> None:
    placeholder = tmp_path / "black.png"
    Image.new("RGB", (1280, 755), (25, 25, 25)).save(placeholder)

    usable = tmp_path / "usable.png"
    image = Image.new("RGB", (1280, 755), "#151923")
    image.paste("#3a8fd8", (80, 80, 720, 650))
    image.paste("#eeeeee", (900, 80, 1220, 220))
    image.save(usable)

    assert not _is_usable_screenshot(placeholder)
    assert _is_usable_screenshot(usable)


def test_docx_save_uses_timestamped_fallback_when_target_is_locked(tmp_path: Path) -> None:
    from aima_ugc.platform.reporting.docx_package import DocxBuilder

    output = tmp_path / "report.docx"
    output.write_bytes(b"old report kept because Word has it open")
    builder = DocxBuilder()
    builder.add_paragraph("新报告")
    real_replace = __import__("os").replace
    calls = 0

    def replace_with_lock(source: object, destination: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError("locked")
        real_replace(source, destination)

    with patch("aima_ugc.platform.reporting.docx_package.os.replace", replace_with_lock):
        actual = builder.save(output)

    assert actual != output
    assert actual.name.startswith("report_")
    assert actual.is_file()
    assert output.read_bytes() == b"old report kept because Word has it open"


def test_docx_rich_table_writes_external_link_and_image(tmp_path: Path) -> None:
    asset = tmp_path / "assets" / "representatives" / "shot.png"
    asset.parent.mkdir(parents=True)
    Image.new("RGB", (80, 60), "white").save(asset)
    markdown_path = tmp_path / "report.md"
    markdown_path.write_text(
        "## 6. 代表性评论与关联页面\n\n"
        "### 6.1 小红书正面评价\n\n"
        "| 原文链接 | 截图 | 评论内容 | 一级标签 | 二级标签 | 行动建议 | 处理进展 |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        "| [打开原文](https://example.com/post) | ![截图](assets/representatives/shot.png) | "
        "评论 | 品牌评价 | 口碑与信任 | 建议跟进 |  |\n",
        encoding="utf-8",
    )
    output = tmp_path / "report.docx"
    summary = convert_markdown_to_docx(markdown_path, output)

    assert summary.image_count == 1
    with zipfile.ZipFile(output) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
        relationships = archive.read("word/_rels/document.xml.rels").decode("utf-8")
        names = archive.namelist()
    assert "https://example.com/post" not in document_xml
    assert 'w:hyperlink r:id="rId2001"' in document_xml
    assert 'Target="https://example.com/post"' in relationships
    assert "word/media/image1.png" in names
    assert document_xml.count("建议跟进") == 1


def test_douyin_screenshot_failure_is_reported_and_does_not_leave_partial_file(
    tmp_path: Path,
) -> None:
    class _FailingPage:
        def goto(self, url: str, **_: object) -> None:
            del url
            raise TimeoutError("page load timed out")

    warnings: list[str] = []
    session = _OptionalScreenshotSession(warnings, target_dir=tmp_path)
    session._page = _FailingPage()  # type: ignore[assignment]
    row = RepresentativeReportRow(
        platform="抖音",
        sentiment="负面",
        content_id="douyin-timeout",
        content_url="https://www.douyin.com/video/1",
        comment_text="",
        primary_label="品牌评价",
        secondary_label="口碑与信任",
        action_advice="建议跟进",
    )

    assert session.fetch(row) is None
    assert not (tmp_path / "screenshots" / "抖音_douyin-timeout.png").exists()
    assert any("抖音截图失败" in warning for warning in warnings)


def test_edge_profile_copy_enters_playwright_path_without_bound_ignore_type_error(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "edge-user-data"
    (source_root / "Default").mkdir(parents=True)
    (source_root / "Default" / "Preferences").write_text("{}", encoding="utf-8")
    (source_root / "Local State").write_text("{}", encoding="utf-8")
    warnings: list[str] = []
    session = _OptionalScreenshotSession(warnings, target_dir=tmp_path / "report")

    with (
        patch(
            "aima_ugc.bootstrap.representative_report_pipeline._find_authenticated_edge_profile",
            return_value=(tmp_path / "msedge.exe", source_root, "Default"),
        ),
        patch.object(session, "_start_playwright_browser") as start_browser,
    ):
        assert session._switch_to_authenticated_browser()

    start_browser.assert_called_once_with(tmp_path / "msedge.exe")
    assert not any("配置复制失败" in warning for warning in warnings)
    session.__exit__(None, None, None)
