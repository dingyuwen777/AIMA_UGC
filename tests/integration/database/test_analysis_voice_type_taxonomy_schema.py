"""Analysis voice_type 数据库只保留结构约束，不复制 Prompt 业务 Taxonomy。"""

from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import inspect


def test_analysis_voice_type_constraint_is_structural_not_fixed_taxonomy() -> None:
    """迁移到 head 后不得存在固定七值 CHECK，但必须拒绝空 voice_type。"""

    runtime = DatabaseRuntime(load_settings())
    try:
        checks = {
            item["name"]: item["sqltext"]
            for item in inspect(runtime.engine).get_check_constraints("analysis_content_results")
        }

        assert "ck_analysis_content_results_voice_type_allowed" not in checks
        assert "ck_analysis_content_results_voice_type_nonempty" in checks
        assert "char_length(voice_type)" in checks[
            "ck_analysis_content_results_voice_type_nonempty"
        ]
    finally:
        runtime.dispose()
