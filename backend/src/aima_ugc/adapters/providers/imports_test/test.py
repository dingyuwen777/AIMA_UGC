"""P1 Excel 离线导入人工入口；只配置参数并调用生产实现。"""

from pathlib import Path

from pydantic import SecretStr

from aima_ugc.adapters.llm import OpenAICompatibleContentLabelingLLM
from aima_ugc.adapters.providers.imports import (
    ExcelConversionSummary,
    convert_excel_to_canonical_jsonl,
)
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentDeduplicationSummary,
    ContentFilterSummary,
    ContentLabelingService,
    OfflineContentLabelingSummary,
    PromptTaxonomyLoader,
    deduplicate_content_jsonl,
    filter_canonical_content_jsonl,
    label_unified_content_jsonl,
)
from aima_ugc.platform.export import (
    ExcelExportSummary,
    export_unified_content_jsonl_to_excel,
)

INPUT_XLSX = Path(r"E:\path\to\source.xlsx")
OUTPUT_ROOT = Path(__file__).with_name("output")

KEYWORDS = ("爱玛",)

SHEET_NAME = "文章"
PROFILE = "aima-monitoring-excel.v1"

ENABLE_REAL_LLM = False
MAX_VALIDATION_RETRIES = 2
LLM_BATCH_SIZE = 20

ENV_FILE = Path(__file__).with_name(".env")


def convert() -> ExcelConversionSummary:
    """执行 XLSX → Canonical JSONL。"""

    return convert_excel_to_canonical_jsonl(
        input_path=INPUT_XLSX,
        output_path=OUTPUT_ROOT / "canonical" / "contents.jsonl",
        profile_name=PROFILE,
        sheet_name=SHEET_NAME,
    )


def filter_keywords() -> ContentFilterSummary:
    """执行 Canonical JSONL → 关键词命中过滤后的统一内容记录。"""

    return filter_canonical_content_jsonl(
        input_path=OUTPUT_ROOT / "canonical" / "contents.jsonl",
        output_path=OUTPUT_ROOT / "filtered" / "contents.jsonl",
        keywords=KEYWORDS,
    )


def deduplicate() -> ContentDeduplicationSummary:
    """执行 filtered JSONL → 稳定身份去重后的统一内容记录。"""

    return deduplicate_content_jsonl(
        input_path=OUTPUT_ROOT / "filtered" / "contents.jsonl",
        output_path=OUTPUT_ROOT / "deduplicated" / "contents.jsonl",
    )


def export_raw_excel() -> ExcelExportSummary:
    """可选导出 deduplicated JSONL 的 raw 人工审阅视图。"""

    return export_unified_content_jsonl_to_excel(
        input_path=OUTPUT_ROOT / "deduplicated" / "contents.jsonl",
        output_path=OUTPUT_ROOT / "raw_data.xlsx",
        include_analysis=False,
    )


def label_sentiment() -> OfflineContentLabelingSummary:
    """显式启用真实 LLM 后，对 deduplicated JSONL 做 P1F 舆情打标。"""

    if not ENABLE_REAL_LLM:
        raise RuntimeError("真实 LLM 默认关闭；确认费用后将 ENABLE_REAL_LLM 改为 True")

    env = _load_env_file(ENV_FILE)
    timeout_seconds = _parse_positive_float(
        env.get("AIMA_LLM_TIMEOUT_SECONDS", "60"),
        name="AIMA_LLM_TIMEOUT_SECONDS",
    )
    use_json_mode = _parse_bool(
        env.get("AIMA_LLM_JSON_MODE", "true"),
        name="AIMA_LLM_JSON_MODE",
    )
    with OpenAICompatibleContentLabelingLLM(
        base_url=_require_env(env, "AIMA_LLM_BASE_URL"),
        api_key=SecretStr(_require_env(env, "AIMA_LLM_API_KEY")),
        model=_require_env(env, "AIMA_LLM_MODEL"),
        provider_name=_require_env(env, "AIMA_LLM_PROVIDER"),
        timeout_seconds=timeout_seconds,
        use_json_mode=use_json_mode,
    ) as llm:
        service = ContentLabelingService(
            prompt_loader=PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH),
            llm=llm,
        )
        return label_unified_content_jsonl(
            input_path=OUTPUT_ROOT / "deduplicated" / "contents.jsonl",
            analysis_dir=OUTPUT_ROOT / "analysis",
            service=service,
            max_validation_retries=MAX_VALIDATION_RETRIES,
            batch_size=LLM_BATCH_SIZE,
        )


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"LLM 配置文件不存在: {path}")

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        if "=" not in line:
            raise ValueError(f"{path}: 第 {line_number} 行不是 KEY=VALUE")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key or key in values:
            raise ValueError(f"{path}: 第 {line_number} 行变量名为空或重复")
        values[key] = _strip_optional_quotes(raw_value.strip())
    return values


def _strip_optional_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _require_env(values: dict[str, str], name: str) -> str:
    value = values.get(name, "")
    if not value or value != value.strip():
        raise ValueError(f"{name} 必须在 ENV_FILE 中配置为非空且已清洗的值")
    return value


def _parse_positive_float(value: str, *, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是数字") from exc
    if parsed <= 0:
        raise ValueError(f"{name} 必须大于 0")
    return parsed


def _parse_bool(value: str, *, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{name} 只允许 true 或 false")


if __name__ == "__main__":
    result = convert()
    print(
        "convert 完成: "
        f"rows_seen={result.rows_seen}, "
        f"rows_written={result.rows_written}, "
        f"rows_rejected={result.rows_rejected}, "
        f"output={result.output_path}"
    )
