#!/usr/bin/env python3
"""为 PR #318 精确补齐 Analysis Runtime Snapshot 配置哈希并生成回归测试。"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_HTTP = ROOT / "backend/src/aima_ugc/bootstrap/content_http.py"
TEST_FILE = ROOT / "tests/unit/content/test_analysis_runtime_configuration_hash.py"


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    """只允许唯一匹配，避免一次性收尾脚本误改无关代码。"""

    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, got {count}")
    return text.replace(old, new, 1)


def patch_content_http() -> None:
    """让 Preview/Create/Idempotency 使用同一安全 Runtime Snapshot 哈希。"""

    text = CONTENT_HTTP.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """                identity = configuration.identity\n                if identity is None:\n                    raise ContentAnalysisUnavailable\n                if isinstance(targets, AnalysisRunTargetSelection) and targets.scope == \"all\":\n""",
        """                identity = configuration.identity\n                llm_provider = configuration.llm_provider\n                if identity is None or llm_provider is None:\n                    raise ContentAnalysisUnavailable\n                runtime_config_snapshot = cast(\n                    dict[str, object], llm_provider.safe_runtime_snapshot()\n                )\n                if isinstance(targets, AnalysisRunTargetSelection) and targets.scope == \"all\":\n""",
        label="preview runtime snapshot",
    )
    text = replace_once(
        text,
        """            configuration_hash=_analysis_configuration_hash(\n                prompt_version=identity.prompt_version,\n                prompt_sha256=identity.prompt_sha256,\n                taxonomy_sha256=identity.taxonomy_sha256,\n                model_provider=identity.model_provider,\n                model=identity.model,\n                generation_config_hash=generation_hash,\n            ),\n""",
        """            configuration_hash=_analysis_configuration_hash(\n                prompt_version=identity.prompt_version,\n                prompt_sha256=identity.prompt_sha256,\n                taxonomy_sha256=identity.taxonomy_sha256,\n                model_provider=identity.model_provider,\n                model=identity.model,\n                generation_config_hash=generation_hash,\n                runtime_config_snapshot=runtime_config_snapshot,\n            ),\n""",
        label="preview configuration hash",
    )
    text = replace_once(
        text,
        """        if identity is None or llm_provider is None:\n            raise ContentAnalysisUnavailable\n        generation_config, generation_hash = current_analysis_generation_config()\n        configuration_hash = _analysis_configuration_hash(\n""",
        """        if identity is None or llm_provider is None:\n            raise ContentAnalysisUnavailable\n        runtime_config_snapshot = cast(\n            dict[str, object], llm_provider.safe_runtime_snapshot()\n        )\n        generation_config, generation_hash = current_analysis_generation_config()\n        configuration_hash = _analysis_configuration_hash(\n""",
        label="create runtime snapshot",
    )
    text = replace_once(
        text,
        """            model_provider=identity.model_provider,\n            model=identity.model,\n            generation_config_hash=generation_hash,\n        )\n        if configuration_hash != expected_configuration_hash:\n""",
        """            model_provider=identity.model_provider,\n            model=identity.model,\n            generation_config_hash=generation_hash,\n            runtime_config_snapshot=runtime_config_snapshot,\n        )\n        if configuration_hash != expected_configuration_hash:\n""",
        label="create configuration hash",
    )
    text = replace_once(
        text,
        """                    generation_config=generation_config,\n                    generation_config_hash=generation_hash,\n                    runtime_config_snapshot=cast(\n                        dict[str, object],\n                        llm_provider.safe_runtime_snapshot(),\n                    ),\n""",
        """                    generation_config=generation_config,\n                    generation_config_hash=generation_hash,\n                    runtime_config_snapshot=runtime_config_snapshot,\n""",
        label="run header runtime snapshot reuse",
    )
    text = replace_once(
        text,
        """def _analysis_configuration_hash(\n    *,\n    prompt_version: str,\n    prompt_sha256: str,\n    taxonomy_sha256: str,\n    model_provider: str,\n    model: str,\n    generation_config_hash: str,\n) -> str:\n    payload = {\n        \"generation_config_hash\": generation_config_hash,\n        \"model\": model,\n        \"model_provider\": model_provider,\n        \"prompt_sha256\": prompt_sha256,\n        \"prompt_version\": prompt_version,\n        \"taxonomy_sha256\": taxonomy_sha256,\n    }\n    encoded = json.dumps(payload, sort_keys=True, separators=(\",\", \":\")).encode(\"utf-8\")\n    return hashlib.sha256(encoded).hexdigest()\n""",
        """def _analysis_configuration_hash(\n    *,\n    prompt_version: str,\n    prompt_sha256: str,\n    taxonomy_sha256: str,\n    model_provider: str,\n    model: str,\n    generation_config_hash: str,\n    runtime_config_snapshot: dict[str, object] | None = None,\n) -> str:\n    \"\"\"计算 Analysis 乐观锁；新 Run 纳入安全 Provider Snapshot，历史空快照保持旧值。\"\"\"\n\n    payload: dict[str, object] = {\n        \"generation_config_hash\": generation_config_hash,\n        \"model\": model,\n        \"model_provider\": model_provider,\n        \"prompt_sha256\": prompt_sha256,\n        \"prompt_version\": prompt_version,\n        \"taxonomy_sha256\": taxonomy_sha256,\n    }\n    if runtime_config_snapshot:\n        payload[\"runtime_config_snapshot\"] = runtime_config_snapshot\n    encoded = json.dumps(payload, sort_keys=True, separators=(\",\", \":\")).encode(\"utf-8\")\n    return hashlib.sha256(encoded).hexdigest()\n""",
        label="configuration hash helper",
    )
    text = replace_once(
        text,
        """        model_provider=cast(str, row[\"model_provider\"]),\n        model=cast(str, row[\"model\"]),\n        generation_config_hash=cast(str, row[\"generation_config_hash\"]),\n    )\n""",
        """        model_provider=cast(str, row[\"model_provider\"]),\n        model=cast(str, row[\"model\"]),\n        generation_config_hash=cast(str, row[\"generation_config_hash\"]),\n        runtime_config_snapshot=cast(\n            dict[str, object], row[\"runtime_config_snapshot\"]\n        ),\n    )\n""",
        label="idempotency runtime snapshot hash",
    )
    CONTENT_HTTP.write_text(text, encoding="utf-8")


def write_tests() -> None:
    """写入 Runtime Snapshot 乐观锁最小回归。"""

    TEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEST_FILE.write_text(
        '''from __future__ import annotations\n\nfrom aima_ugc.bootstrap.content_http import _analysis_configuration_hash\n\n\ndef _configuration_hash(runtime_config_snapshot: dict[str, object] | None) -> str:\n    \"\"\"使用稳定基础身份计算测试 hash。\"\"\"\n\n    return _analysis_configuration_hash(\n        prompt_version=\"scheme-v1\",\n        prompt_sha256=\"a\" * 64,\n        taxonomy_sha256=\"b\" * 64,\n        model_provider=\"api.deepseek.com\",\n        model=\"deepseek-v4-pro\",\n        generation_config_hash=\"c\" * 64,\n        runtime_config_snapshot=runtime_config_snapshot,\n    )\n\n\ndef test_runtime_provider_revision_changes_analysis_configuration_hash() -> None:\n    first = {\n        \"provider_config_id\": \"11111111-1111-4111-8111-111111111111\",\n        \"provider_kind\": \"llm\",\n        \"provider\": \"api.deepseek.com\",\n        \"base_url\": \"https://api.deepseek.com/v1\",\n        \"secret_ref\": \"providers/llm/key-1.key\",\n        \"model\": \"deepseek-v4-pro\",\n        \"timeout_seconds\": 45,\n        \"max_retries\": 1,\n        \"max_concurrency\": 5,\n        \"max_rps\": None,\n        \"extra_config\": {},\n        \"revision\": 1,\n    }\n    second = {**first, \"secret_ref\": \"providers/llm/key-2.key\", \"revision\": 2}\n\n    assert _configuration_hash(first) != _configuration_hash(second)\n\n\ndef test_empty_runtime_snapshot_preserves_legacy_analysis_configuration_hash() -> None:\n    assert _configuration_hash(None) == _configuration_hash({})\n''',
        encoding="utf-8",
    )


def main() -> int:
    """应用补丁并运行与本 Finding 直接相关的验证。"""

    patch_content_http()
    write_tests()
    subprocess.run(
        [
            "uv",
            "run",
            "ruff",
            "format",
            str(CONTENT_HTTP.relative_to(ROOT)),
            str(TEST_FILE.relative_to(ROOT)),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            "uv",
            "run",
            "ruff",
            "check",
            str(CONTENT_HTTP.relative_to(ROOT)),
            str(TEST_FILE.relative_to(ROOT)),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(["uv", "run", "mypy", "backend/src"], cwd=ROOT, check=True)
    subprocess.run(
        ["uv", "run", "pytest", str(TEST_FILE.relative_to(ROOT)), "-q"],
        cwd=ROOT,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
