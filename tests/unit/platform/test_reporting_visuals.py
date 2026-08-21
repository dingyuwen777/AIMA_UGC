from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from aima_ugc.platform.reporting import generate_excel_report
from aima_ugc.platform.reporting.visuals import wordcloud
from openpyxl import Workbook
from PIL import Image, ImageChops

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_visual_workbook(path: Path) -> None:
    workbook = Workbook()
    content = workbook.active
    content.title = "内容"
    content.append(("平台", "发布时间", "命中关键词", "情感标签", "一级标签", "二级标签"))
    rows = (
        ("douyin", "2026-08-18 08:00:00", "爱玛；新品", "正面", "品牌评价", "口碑与信任"),
        ("xiaohongshu", "2026-08-18 09:00:00", "爱玛；颜值", "中性", "外观设计", "整体造型与颜值"),
        ("weibo", "2026-08-19 10:00:00", "爱玛；售后", "负面", "售后服务", "客服与服务态度"),
        ("bilibili", "2026-08-19 11:00:00", "爱玛；续航", "混合", "电池、续航与充电", "续航表现"),
    )
    for row in rows:
        content.append(row)
    labels = workbook.create_sheet("标签明细")
    labels.append(("平台", "情感标签", "一级标签", "二级标签"))
    for platform, _published, _keywords, sentiment, primary, secondary in rows:
        labels.append((platform, sentiment, primary, secondary))
    comments = workbook.create_sheet("评论")
    comments.append(("平台",))
    comments.append(("douyin",))
    workbook.save(path)
    workbook.close()


def _non_white_ratio(path: Path) -> float:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
    white = Image.new("RGB", rgb.size, "white")
    difference = ImageChops.difference(rgb, white).convert("L")
    histogram = difference.histogram()
    changed = sum(histogram[5:])
    total = rgb.width * rgb.height
    difference.close()
    white.close()
    rgb.close()
    return changed / total


def test_wordcloud_is_deterministic_and_reacts_to_frequency_changes(tmp_path: Path) -> None:
    font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if not font.is_file():
        pytest.skip("当前测试环境未安装 Noto Sans CJK")
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    changed = tmp_path / "changed.png"
    frequencies = {"品牌评价": 100, "价格与价值": 36, "外观设计": 25, "售后服务": 9}
    wordcloud.render_wordcloud_png(frequencies, first)
    wordcloud.render_wordcloud_png(frequencies, second)
    wordcloud.render_wordcloud_png({**frequencies, "售后服务": 81}, changed)
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() != changed.read_bytes()
    with Image.open(first) as image:
        image.verify()
    with Image.open(first) as image:
        assert image.size == (1600, 900)
        assert image.info.get("dpi", (0, 0))[0] >= 250
    # 少词词云最容易显得空和廉价，因此对稀疏样例要求更高的有效字形占比。
    assert _non_white_ratio(first) >= 0.075


def test_wordcloud_dense_keywords_remains_restrained_but_visually_full(tmp_path: Path) -> None:
    font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if not font.is_file():
        pytest.skip("当前测试环境未安装 Noto Sans CJK")
    frequencies = {"爱玛": 44000}
    frequencies.update({f"车型 {index:02d}": max(1, 500 - index * 11) for index in range(1, 56)})
    output = tmp_path / "dense.png"

    wordcloud.render_wordcloud_png(frequencies, output)

    with Image.open(output) as image:
        image.verify()
    # 多词云需要保留词间呼吸感，不能为了追求像素填充率把文字挤成一团。
    assert _non_white_ratio(output) >= 0.07


def test_wordcloud_fails_closed_when_cjk_font_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AIMA_REPORT_CJK_FONT", str(tmp_path / "missing.ttf"))
    monkeypatch.setattr(wordcloud, "_candidate_font_paths", lambda: ())
    with pytest.raises(RuntimeError, match="未找到可用中文字体"):
        wordcloud.render_wordcloud_png({"品牌评价": 10}, tmp_path / "cloud.png")


def test_default_report_generates_landscape_ranking_and_wordcloud_assets(tmp_path: Path) -> None:
    workbook_path = tmp_path / "labeled_data.xlsx"
    _make_visual_workbook(workbook_path)
    before = _sha256(workbook_path)

    summary = generate_excel_report(input_path=workbook_path, output_dir=tmp_path / "reports")

    assert _sha256(workbook_path) == before
    markdown = summary.markdown_path.read_text(encoding="utf-8")
    assert "<!-- aima:table-style=kpi -->" in markdown
    assert markdown.count("<!-- aima:table-style=ranking -->") >= 9
    assert "![一级议题词云](assets/primary_topics_wordcloud.png)" in markdown
    assert "![热点关键词词云](assets/keyword_wordcloud.png)" in markdown
    assert "<!-- aima:chart-presentation=sentiment-split -->" in markdown

    assets = summary.markdown_path.parent / "assets"
    for name in ("primary_topics_wordcloud.png", "keyword_wordcloud.png"):
        path = assets / name
        assert path.is_file()
        with Image.open(path) as image:
            image.verify()

    with zipfile.ZipFile(summary.word_path) as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
        assert "word/media/image1.png" in names
        assert "word/media/image2.png" in names
        document = ET.fromstring(archive.read("word/document.xml"))
        page = document.find(f".//{{{_W}}}sectPr/{{{_W}}}pgSz")
        assert page is not None
        assert page.get(f"{{{_W}}}orient") == "landscape"
        assert "01" in archive.read("word/document.xml").decode("utf-8")
        chart_parts = sorted(
            name for name in names if name.startswith("word/charts/chart") and name.endswith(".xml")
        )
        assert len(chart_parts) >= 2
