from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

from aima_ugc.platform import reporting
from openpyxl import Workbook, load_workbook

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _make_minimal_workbook(path: Path) -> None:
    workbook = Workbook()
    content = workbook.active
    content.title = "内容"
    content.append(("平台", "发布时间", "命中关键词", "情感标签", "一级标签", "二级标签"))
    content.append(("抖音", "2026-08-20 10:00:00", "爱玛", "负面", "售后服务", "客服与服务态度"))
    content.append(
        ("小红书", "2026-08-20 11:00:00", "爱玛；新品", "正面", "品牌评价", "口碑与信任")
    )

    labels = workbook.create_sheet("标签明细")
    labels.append(("平台", "情感标签", "一级标签", "二级标签", "发布时间"))
    labels.append(("抖音", "负面", "售后服务", "客服与服务态度", "2026-08-20 10:00:00"))
    labels.append(("小红书", "正面", "品牌评价", "口碑与信任", "2026-08-20 11:00:00"))

    comments = workbook.create_sheet("评论")
    comments.append(("平台", "评论时间"))
    comments.append(("抖音", "2026-08-20 10:30:00"))

    workbook.save(path)
    workbook.close()


def test_reporting_owns_default_markdown_template(tmp_path: Path) -> None:
    expected_template = Path(reporting.__file__).with_name("report_template.md")

    assert reporting.DEFAULT_REPORT_TEMPLATE_PATH == expected_template
    assert reporting.DEFAULT_REPORT_TEMPLATE_PATH.is_file()

    workbook_path = tmp_path / "labeled_data.xlsx"
    _make_minimal_workbook(workbook_path)

    summary = reporting.generate_excel_report(
        input_path=workbook_path,
        output_dir=tmp_path / "reports",
    )

    assert summary.template_path == expected_template
    assert summary.markdown_path.is_file()
    assert summary.word_path.is_file()


def test_default_report_is_ready_for_management_presentation(tmp_path: Path) -> None:
    workbook_path = tmp_path / "labeled_data.xlsx"
    _make_minimal_workbook(workbook_path)

    summary = reporting.generate_excel_report(
        input_path=workbook_path,
        output_dir=tmp_path / "reports",
    )
    markdown = summary.markdown_path.read_text(encoding="utf-8")

    assert markdown.startswith("# 爱玛品牌舆情分析报告")
    assert "## 1. 总体概况" in markdown
    assert "## 2. 平台声量与情感结构" in markdown
    assert "## 3. 情感表现" in markdown
    assert "## 4. 核心议题分析" in markdown
    assert "## 5. 热点关键词" in markdown
    assert "### 1.3 与上周期对比" in markdown
    assert "未提供与本期等长的上期统一数据" in markdown
    assert "平台 × 情感" in markdown
    assert "正面内容" in markdown
    assert "负面内容" in markdown
    assert "### 3.3 正面一级议题" in markdown
    assert "### 3.6 负面二级议题" in markdown
    assert "客服与服务态度" in markdown
    assert (summary.markdown_path.parent / "assets" / "secondary_topics_wordcloud.png").is_file()
    for template_annotation in (
        "这种展示方式比较好",
        "建议展示在一张图片",
        "可以参考这种展示方式",
        "二级议题词云（缺失）",
    ):
        assert template_annotation not in markdown
    assert "## 7. 数据概览与趋势明细" not in markdown

    implementation_terms = ("Excel", "Sheet", "Markdown", "Word", "模板", "Canonical", "Exporter")
    assert all(term not in markdown for term in implementation_terms)


def test_default_report_compares_the_matching_previous_period(tmp_path: Path) -> None:
    current_path = tmp_path / "current.xlsx"
    previous_path = tmp_path / "previous.xlsx"
    _make_minimal_workbook(current_path)
    _make_minimal_workbook(previous_path)

    previous = load_workbook(previous_path)
    for sheet_name, column in (("内容", "B"), ("标签明细", "E"), ("评论", "B")):
        sheet = previous[sheet_name]
        for row in range(2, sheet.max_row + 1):
            sheet[f"{column}{row}"] = str(sheet[f"{column}{row}"].value).replace(
                "2026-08-20", "2026-08-13"
            )
    previous.save(previous_path)
    previous.close()

    current = load_workbook(current_path)
    current["内容"].append(
        ("抖音", "2026-08-20 12:00:00", "爱玛", "负面", "品牌评价", "口碑与信任")
    )
    current["标签明细"].append(
        ("抖音", "负面", "品牌评价", "口碑与信任", "2026-08-20 12:00:00")
    )
    current["评论"].append(("抖音", "2026-08-20 12:30:00"))
    current.save(current_path)
    current.close()

    summary = reporting.generate_excel_report(
        input_path=current_path,
        output_dir=tmp_path / "reports",
        report_date_range=(date(2026, 8, 20), date(2026, 8, 26)),
        previous_input_path=previous_path,
    )
    markdown = summary.markdown_path.read_text(encoding="utf-8")
    comparison = markdown.split("### 1.3 与上周期对比", 1)[1].split("## 2.", 1)[0]

    assert "| 指标 | 本期 | 上期 | 变化情况 |" in comparison
    assert "| 总声量 | 3 | 2 | 上升 50.00% |" in comparison
    assert "| TOP1 正面议题 | 品牌评价 | 品牌评价 | 保持第一 |" in comparison
    assert "| TOP1 负面议题 | 品牌评价 | 售后服务 | 由“售后服务”变为“品牌评价” |" in comparison


def test_default_report_uses_portrait_page_and_requested_chart_groups(
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "labeled_data.xlsx"
    _make_minimal_workbook(workbook_path)
    workbook = load_workbook(workbook_path)
    content = workbook["内容"]
    labels = workbook["标签明细"]
    for platform in ("快手", "微博", "哔哩哔哩"):
        content.append((platform, "2026-08-20 12:00:00", "爱玛", "中性", "品牌评价", "口碑与信任"))
        labels.append((platform, "中性", "品牌评价", "口碑与信任", "2026-08-20 12:00:00"))
    workbook.save(workbook_path)
    workbook.close()

    summary = reporting.generate_excel_report(
        input_path=workbook_path,
        output_dir=tmp_path / "reports",
    )

    with zipfile.ZipFile(summary.word_path) as archive:
        document_xml = archive.read("word/document.xml")
        document = ET.fromstring(document_xml)
        page_size = document.find(f".//{{{_W}}}sectPr/{{{_W}}}pgSz")
        page_margins = document.find(f".//{{{_W}}}sectPr/{{{_W}}}pgMar")
        chart_xml = [
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.startswith("word/charts/chart") and name.endswith(".xml")
        ]

    assert page_size is not None
    assert page_size.get(f"{{{_W}}}w") == "11906"
    assert page_size.get(f"{{{_W}}}h") == "16838"
    assert page_size.get(f"{{{_W}}}orient") is None
    assert page_margins is not None
    assert page_margins.get(f"{{{_W}}}left") == "1800"
    assert page_margins.get(f"{{{_W}}}top") == "1440"
    markdown = summary.markdown_path.read_text(encoding="utf-8")
    assert sum("平台 × 情感结构" in xml for xml in chart_xml) == 1
    platform_sentiment_xml = next(xml for xml in chart_xml if "平台 × 情感结构" in xml)
    assert 'barDir val="col"' in platform_sentiment_xml
    assert 'showVal val="1"' in platform_sentiment_xml
    assert sum("抖音平台每日内容量" in xml for xml in chart_xml) == 1
    assert sum("其他平台每日内容量" in xml for xml in chart_xml) == 1
    assert sum("正面、中性每日趋势" in xml for xml in chart_xml) == 1
    assert sum("负面、混合每日趋势" in xml for xml in chart_xml) == 1
    assert '%% series ["抖音"]' in markdown
    other_platform_chart = markdown.split('title "其他平台每日内容量"', 1)[1].split("```", 1)[0]
    assert "抖音" not in other_platform_chart
    for platform in ("小红书", "快手", "微博", "哔哩哔哩"):
        assert platform in other_platform_chart
    assert '%% series ["正面", "中性"]' in markdown
    assert '%% series ["负面"]' in markdown
    for heading in (
        "### 3.3 正面一级议题",
        "### 3.4 正面二级议题",
        "### 3.5 负面一级议题",
        "### 3.6 负面二级议题",
    ):
        section = markdown.split(heading, 1)[1].split("\n### ", 1)[0]
        assert "| " not in section
        assert "%% bar-direction horizontal" in section
        assert '%% series ["数量"]' in section
    assert "完整明细" not in markdown
    assert "AIMARankingChart" not in document_xml.decode("utf-8")
    assert "完整明细" not in document_xml.decode("utf-8")
