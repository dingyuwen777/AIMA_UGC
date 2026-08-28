from aima_ugc.modules.analysis.tables import analysis_content_results_table
from sqlalchemy import CheckConstraint


def test_analysis_result_schema_persists_relevance_and_voice_type() -> None:
    columns = analysis_content_results_table.c

    assert "relevance" in columns
    assert columns.relevance.nullable is False
    assert "voice_type" in columns
    assert columns.voice_type.nullable is False
    assert columns.sentiment.nullable is True

    check_sql = {
        str(constraint.sqltext)
        for constraint in analysis_content_results_table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "relevance in ('relevant','irrelevant')" in check_sql
    assert "char_length(voice_type) > 0" in check_sql
    assert not any("voice_type in" in expression for expression in check_sql)
    # 数据库也必须强制 V3 条件结构，不能只依赖 LLM Prompt 或 Pydantic Validator。
    assert any(
        "relevance = 'relevant'" in expression
        and "sentiment is not null" in expression
        and "relevance = 'irrelevant'" in expression
        and "sentiment is null" in expression
        for expression in check_sql
    )
