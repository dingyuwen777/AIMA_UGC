"""一次性把当前发声类型集成测试 Fixture 改为 Prompt Taxonomy 驱动。"""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    """读取 UTF-8 文本。"""

    return Path(path).read_text(encoding="utf-8")


def _write(path: str, text: str) -> None:
    """写回 UTF-8 文本。"""

    Path(path).write_text(text, encoding="utf-8")


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    """要求目标文本唯一命中，避免基于错误仓库状态继续修改。"""

    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def _update_bidirectional_review() -> None:
    """双向人工相关性复核 Fixture 使用当前 Taxonomy 合法值。"""

    path = "tests/integration/content/test_bidirectional_relevance_review.py"
    text = _read(path)
    old = '''    service = ContentLabelingService(
        prompt_loader=FrozenPromptTaxonomyLoader(taxonomy),
        llm=FakeContentLabelingLLM(
            responses=[
                '{"items":[{"item_no":1,"relevance":"relevant",'
                '"voice_type":"user_voice","sentiment":"中性",'
                '"labels":[{"primary_label":"骑行性能","secondary_label":"舒适性"}]}]}'
            ]
        ),
    )'''
    new = '''    response = (
        '{"items":[{"item_no":1,"relevance":"relevant","voice_type":"'
        + taxonomy.voice_types[0]
        + '","sentiment":"中性","labels":['
        '{"primary_label":"骑行性能","secondary_label":"舒适性"}]}]}'
    )
    service = ContentLabelingService(
        prompt_loader=FrozenPromptTaxonomyLoader(taxonomy),
        llm=FakeContentLabelingLLM(responses=[response]),
    )'''
    _write(path, _replace_once(text, old, new, "bidirectional registry"))


def _update_manual_review() -> None:
    """人工相关性复核 Fixture 不再写死旧英文类别。"""

    path = "tests/integration/content/test_manual_relevance_review.py"
    text = _read(path)
    old = '''def _irrelevant_response() -> str:
    return (
        '{"items":[{"item_no":1,"relevance":"irrelevant",'
        '"voice_type":"media_information","sentiment":null,"labels":[]}]}'
    )'''
    new = '''def _irrelevant_response() -> str:
    """返回使用当前 Prompt Taxonomy 合法发声类型的 irrelevant Fixture。"""

    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    return (
        '{"items":[{"item_no":1,"relevance":"irrelevant","voice_type":"'
        + taxonomy.voice_types[0]
        + '","sentiment":null,"labels":[]}]}'
    )'''
    _write(path, _replace_once(text, old, new, "manual relevance response"))


def _update_stage12() -> None:
    """Stage12 Analysis Run Fixture 使用当前 Taxonomy 合法值。"""

    path = "tests/integration/content/test_stage12_analysis_runs.py"
    text = _read(path)
    old = '''def _response(sentiment: str) -> str:
    return (
        '{"items":[{"item_no":1,"relevance":"relevant",'
        '"voice_type":"user_voice","sentiment":"'
        + sentiment
        + '","labels":[{"primary_label":"骑行性能",'
        '"secondary_label":"舒适性"}]}]}'
    )'''
    new = '''def _response(sentiment: str) -> str:
    """返回使用当前 Prompt Taxonomy 合法发声类型的 Analysis Fixture。"""

    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    return (
        '{"items":[{"item_no":1,"relevance":"relevant","voice_type":"'
        + taxonomy.voice_types[0]
        + '","sentiment":"'
        + sentiment
        + '","labels":[{"primary_label":"骑行性能",'
        '"secondary_label":"舒适性"}]}]}'
    )'''
    _write(path, _replace_once(text, old, new, "stage12 response"))


def _update_stage8d() -> None:
    """Stage8D Fixture、断言和筛选全部引用当前 Taxonomy 值。"""

    path = "tests/integration/content/test_stage8d_voice_plaza_runtime.py"
    text = _read(path)
    marker = '''from sqlalchemy import func, select, update


def _xlsx'''
    replacement = '''from sqlalchemy import func, select, update

_CURRENT_TAXONOMY = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
_CURRENT_VOICE_TYPE = _CURRENT_TAXONOMY.voice_types[0]


def _xlsx'''
    text = _replace_once(text, marker, replacement, "stage8d taxonomy constants")
    text = _replace_once(
        text,
        'def _relevant_response(*, sentiment: str = "负面", voice_type: str = "user_voice") -> str:',
        'def _relevant_response(*, sentiment: str = "负面", voice_type: str = _CURRENT_VOICE_TYPE) -> str:',
        "stage8d relevant default",
    )
    text = _replace_once(
        text,
        'def _irrelevant_response(*, voice_type: str = "media_information") -> str:',
        'def _irrelevant_response(*, voice_type: str = _CURRENT_VOICE_TYPE) -> str:',
        "stage8d irrelevant default",
    )
    if text.count('== "user_voice"') != 2:
        raise RuntimeError("stage8d expected exactly two current user_voice assertions")
    text = text.replace('== "user_voice"', '== _CURRENT_VOICE_TYPE')
    text = _replace_once(
        text,
        '                voice_type="user_voice",',
        '                voice_type=_CURRENT_VOICE_TYPE,',
        "stage8d voice filter",
    )
    stale_old = '''                        '{"items":[{"item_no":1,"relevance":"relevant",'
                        '"voice_type":"user_voice","sentiment":"中性","labels":['''
    stale_new = '''                        '{"items":[{"item_no":1,"relevance":"relevant","voice_type":"'
                        + _CURRENT_VOICE_TYPE
                        + '","sentiment":"中性","labels":['''
    text = _replace_once(text, stale_old, stale_new, "stage8d stale response")
    _write(path, text)


def _scan_current_runtime_literals() -> None:
    """确认当前运行时代码与回归链不再把旧英文值当现行合法分类。"""

    roots = [
        Path("backend/src"),
        Path("tests/integration/content"),
        Path("tests/fullstack"),
        Path("scripts/performance/benchmark_p1_offline.py"),
    ]
    legacy_values = (
        "user_voice",
        "creator_marketing",
        "brand_official",
        "dealer_promotion",
        "media_information",
        "other_organization",
    )
    violations: list[str] = []
    for root in roots:
        candidates = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for candidate in candidates:
            if candidate.suffix not in {".py", ".md", ".ts", ".vue"}:
                continue
            body = candidate.read_text(encoding="utf-8")
            for value in legacy_values:
                if f'"{value}"' in body or f"'{value}'" in body:
                    violations.append(f"{candidate}: {value}")
    if violations:
        raise RuntimeError("current legacy voice_type literals remain:\n" + "\n".join(violations))


def main() -> None:
    """执行 Fixture 迁移并扫描遗留当前值。"""

    _update_bidirectional_review()
    _update_manual_review()
    _update_stage12()
    _update_stage8d()
    _scan_current_runtime_literals()


if __name__ == "__main__":
    main()
