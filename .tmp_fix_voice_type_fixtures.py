"""一次性迁移发声类型测试/Benchmark Fixture；成功后由 Workflow 删除。"""

from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str, *, label: str) -> None:
    """要求目标文本唯一命中后替换，避免覆盖未知新状态。"""

    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path} {label}: 预期 1 次，实际 {count} 次")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(path: Path, old: str, new: str, *, expected: int, label: str) -> None:
    """要求目标文本命中固定次数后全部替换。"""

    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{path} {label}: 预期 {expected} 次，实际 {count} 次")
    path.write_text(text.replace(old, new), encoding="utf-8")


def update_relevance_voice_tests() -> None:
    """让 V3 Service Fixture 使用当前 Prompt Taxonomy，而结构 Contract 仍验证字符串开放性。"""

    path = Path("tests/unit/analysis/test_analysis_relevance_voice_v3.py")
    text = path.read_text(encoding="utf-8")
    marker = "def test_v3_contract_enforces_relevance_dependent_shape_and_voice_type() -> None:\n"
    if marker not in text:
        raise RuntimeError("V3 Contract 测试入口不存在")
    text = text.replace(
        marker,
        marker + "    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()\n",
        1,
    )
    marker = "def test_service_accepts_irrelevant_without_forcing_sentiment_or_labels() -> None:\n    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)\n"
    if marker not in text:
        raise RuntimeError("irrelevant Service 测试入口不存在")
    text = text.replace(marker, marker + "    taxonomy = loader.load()\n", 1)
    counts = {
        'voice_type="user_voice",': 4,
        'voice_type="media_information",': 3,
        'voice_type="unknown",': 2,
        'assert analysis.voice_type == "user_voice"': 1,
    }
    for old, expected in counts.items():
        actual = text.count(old)
        if actual != expected:
            raise RuntimeError(f"V3 Fixture {old}: 预期 {expected} 次，实际 {actual} 次")
    text = text.replace('voice_type="user_voice",', "voice_type=taxonomy.voice_types[0],")
    text = text.replace('voice_type="media_information",', "voice_type=taxonomy.voice_types[5],")
    text = text.replace('voice_type="unknown",', "voice_type=taxonomy.voice_types[-1],")
    text = text.replace(
        'assert analysis.voice_type == "user_voice"',
        "assert analysis.voice_type == taxonomy.voice_types[0]",
    )
    path.write_text(text, encoding="utf-8")


def update_content_labeling_tests() -> None:
    """让通用 ContentLabeling Fixture 的合法发声类型来自当前 Taxonomy。"""

    path = Path("tests/unit/analysis/test_content_labeling.py")
    text = path.read_text(encoding="utf-8")
    old = '"voice_type": "unknown",'
    count = text.count(old)
    if count < 3:
        raise RuntimeError(f"ContentLabeling old unknown fixture 过少: {count}")
    path.write_text(text.replace(old, '"voice_type": taxonomy.voice_types[-1],'), encoding="utf-8")

    path = Path("tests/unit/analysis/test_content_labeling_validation.py")
    replace_once(
        path,
        '"voice_type": "unknown",',
        '"voice_type": taxonomy.voice_types[-1],',
        label="validation helper voice_type",
    )

    path = Path("tests/unit/analysis/test_multilabel_analysis_v2.py")
    replace_all(
        path,
        '"voice_type": "unknown",',
        '"voice_type": taxonomy.voice_types[-1],',
        expected=3,
        label="multilabel current voice_type",
    )


def update_offline_tests() -> None:
    """让离线链与 checkpoint Fixture 使用当前合法 voice_type。"""

    for relative, expected in (
        ("tests/unit/analysis/test_offline_content_labeling.py", 2),
        ("tests/unit/analysis/test_offline_labeling_concurrency.py", 1),
        ("tests/unit/analysis/test_p1g_checkpoint_recovery.py", 1),
    ):
        replace_all(
            Path(relative),
            '"voice_type": "user_voice",',
            '"voice_type": taxonomy.voice_types[0],',
            expected=expected,
            label="offline current voice_type",
        )


def update_benchmark_fixture() -> None:
    """性能 Fake 也从 Prompt Taxonomy 取当前 voice_type，不复制业务值。"""

    path = Path("scripts/performance/benchmark_p1_offline.py")
    replace_once(
        path,
        "        self._sentiment = taxonomy.sentiments[0]\n",
        "        self._voice_type = taxonomy.voice_types[0]\n        self._sentiment = taxonomy.sentiments[0]\n",
        label="benchmark voice type snapshot",
    )
    replace_once(
        path,
        '                    "voice_type": "user_voice",',
        '                    "voice_type": self._voice_type,',
        label="benchmark response voice_type",
    )


def update_excel_tests() -> None:
    """Excel 当前值直接使用中文；历史缺失值与旧英文值保持原始事实。"""

    path = Path("tests/unit/platform/test_excel_export.py")
    replace_once(
        path,
        '                voice_type="creator_marketing",',
        '                voice_type="营销推广发声",',
        label="Excel current fixture",
    )
    replace_once(
        path,
        '            "达人/创作者营销",',
        '            "营销推广发声",',
        label="Excel current expected value",
    )

    path = Path("tests/unit/platform/test_p1g_labeled_excel.py")
    replace_once(
        path,
        "        # V1 历史结果没有 voice_type，兼容导出必须明确展示为“无法判断”。\n",
        "        # V1 历史结果没有 voice_type，不应为历史事实补造当前分类。\n",
        label="V1 comment",
    )
    replace_once(
        path,
        '            "无法判断",\n            "正面",',
        '            None,\n            "正面",',
        label="V1 missing voice_type expectation",
    )


def tighten_prompt_legacy_assertion() -> None:
    """只检查 Prompt 中精确旧 JSON 字符串，避免错误码子串造成误报。"""

    path = Path("tests/unit/analysis/test_prompt_judgment_tables.py")
    replace_once(
        path,
        "        assert legacy_value not in prompt\n",
        "        assert f'\"{legacy_value}\"' not in prompt\n",
        label="legacy value exact check",
    )


def main() -> None:
    """执行全部 Fixture 迁移。"""

    update_relevance_voice_tests()
    update_content_labeling_tests()
    update_offline_tests()
    update_benchmark_fixture()
    update_excel_tests()
    tighten_prompt_legacy_assertion()


if __name__ == "__main__":
    main()
