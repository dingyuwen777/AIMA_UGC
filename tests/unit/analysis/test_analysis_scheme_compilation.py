"""Analysis Scheme 编译快照稳定性回归。"""

from aima_ugc.contracts.administration import AnalysisSchemeDefinitionRequest
from aima_ugc.modules.analysis.schemes import compile_analysis_scheme


def test_compile_analysis_scheme_is_stable_across_jsonb_object_key_order() -> None:
    """JSONB 不保留对象键顺序，编译结果不能依赖 labels 的插入顺序。"""

    common = {
        "prompt_template": "请按以下分类输出：\n{{AIMA_TAXONOMY_JSON}}",
        "sentiments": ("正面", "无法判断"),
        "voice_types": ("真实用户发声", "无法判断"),
    }
    original = AnalysisSchemeDefinitionRequest(
        **common,
        labels={
            "无法分类": ("无法判断",),
            "产品体验": ("续航表现",),
        },
    )
    jsonb_round_trip = AnalysisSchemeDefinitionRequest(
        **common,
        labels={
            "产品体验": ("续航表现",),
            "无法分类": ("无法判断",),
        },
    )

    compiled_original = compile_analysis_scheme(original)
    compiled_round_trip = compile_analysis_scheme(jsonb_round_trip)

    assert compiled_original.prompt_text == compiled_round_trip.prompt_text
    assert compiled_original.prompt_sha256 == compiled_round_trip.prompt_sha256
    assert compiled_original.taxonomy_sha256 == compiled_round_trip.taxonomy_sha256
