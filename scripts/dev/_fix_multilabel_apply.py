from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

excel_path = ROOT / "backend/src/aima_ugc/platform/export/excel.py"
excel_text = excel_path.read_text(encoding="utf-8")
replacements = {
    'primary_label = "\n".join': r'primary_label = "\n".join',
    'secondary_label = "\n".join': r'secondary_label = "\n".join',
}
for broken, fixed in replacements.items():
    count = excel_text.count(broken)
    if count != 1:
        raise RuntimeError(f"expected one broken newline literal, got {count}: {broken!r}")
    excel_text = excel_text.replace(broken, fixed, 1)
excel_path.write_text(excel_text, encoding="utf-8")

labeling_path = ROOT / "backend/src/aima_ugc/modules/analysis/content_labeling.py"
labeling_text = labeling_path.read_text(encoding="utf-8")
old_labels_type = "    labels: tuple[_ModelLabelPair, ...] = Field(min_length=1)"
new_labels_type = "    labels: list[_ModelLabelPair] = Field(min_length=1)"
if labeling_text.count(old_labels_type) != 1:
    raise RuntimeError("expected one strict tuple model labels declaration")
labeling_text = labeling_text.replace(old_labels_type, new_labels_type, 1)
old_parser = '''    if "labels" in value:
        parsed = _ModelLabelItemV2.model_validate(value)
        return parsed.sentiment, tuple(
            ContentLabelPairV2(
                primary_label=pair.primary_label,
                secondary_label=pair.secondary_label,
            )
            for pair in parsed.labels
        )
    parsed = _ModelLabelItemV1.model_validate(value)
    return parsed.sentiment, (
        ContentLabelPairV2(
            primary_label=parsed.primary_label,
            secondary_label=parsed.secondary_label,
        ),
    )
'''
new_parser = '''    if "labels" in value:
        parsed_v2 = _ModelLabelItemV2.model_validate(value)
        return parsed_v2.sentiment, tuple(
            ContentLabelPairV2(
                primary_label=pair.primary_label,
                secondary_label=pair.secondary_label,
            )
            for pair in parsed_v2.labels
        )
    parsed_v1 = _ModelLabelItemV1.model_validate(value)
    return parsed_v1.sentiment, (
        ContentLabelPairV2(
            primary_label=parsed_v1.primary_label,
            secondary_label=parsed_v1.secondary_label,
        ),
    )
'''
if labeling_text.count(old_parser) != 1:
    raise RuntimeError("expected one V1/V2 parser block")
labeling_text = labeling_text.replace(old_parser, new_parser, 1)
labeling_path.write_text(labeling_text, encoding="utf-8")

offline_path = ROOT / "backend/src/aima_ugc/modules/analysis/offline_labeling.py"
offline_text = offline_path.read_text(encoding="utf-8")
old_adapter = "_ANALYSIS_ADAPTER = TypeAdapter(ContentLabelAnalysis)"
new_adapter = (
    "_ANALYSIS_ADAPTER: TypeAdapter[ContentLabelAnalysis] = "
    "TypeAdapter(ContentLabelAnalysis)"
)
if offline_text.count(old_adapter) != 1:
    raise RuntimeError("expected one analysis TypeAdapter declaration")
offline_text = offline_text.replace(old_adapter, new_adapter, 1)
offline_path.write_text(offline_text, encoding="utf-8")

test_path = ROOT / "tests/unit/platform/test_multilabel_excel.py"
test_text = test_path.read_text(encoding="utf-8")
old_assertion = '        assert label_sheet.max_row == 1\n'
new_assertion = '''        header = next(label_sheet.iter_rows(min_row=1, max_row=1, values_only=True))
        assert header == (
            "内容ID",
            "平台",
            "标题",
            "情感标签",
            "一级标签",
            "二级标签",
            "内容链接",
        )
        assert next(label_sheet.iter_rows(min_row=2, values_only=True), None) is None
'''
if test_text.count(old_assertion) != 1:
    raise RuntimeError("expected one raw label detail max_row assertion")
test_text = test_text.replace(old_assertion, new_assertion, 1)
test_path.write_text(test_text, encoding="utf-8")

print("multilabel generated fixes applied")
