from __future__ import annotations

from pathlib import Path

from aima_ugc.entrypoints.api_main import create_app
from aima_ugc.platform.health import ReadinessReport
from fastapi.testclient import TestClient


def _configure_base_runtime(monkeypatch, tmp_path: Path) -> Path:  # type: ignore[no-untyped-def]
    data_dir = tmp_path / "data"
    log_dir = tmp_path / "logs"
    secret_dir = tmp_path / "secrets"
    for path in (data_dir, log_dir, secret_dir):
        path.mkdir(parents=True)
    monkeypatch.setenv("AIMA_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AIMA_LOG_DIR", str(log_dir))
    monkeypatch.setenv("AIMA_SECRET_DIR", str(secret_dir))
    monkeypatch.delenv("AIMA_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("AIMA_LLM_PROVIDER_NAME", raising=False)
    monkeypatch.delenv("AIMA_LLM_MODEL", raising=False)
    return secret_dir


def _app() -> TestClient:
    return TestClient(
        create_app(
            readiness_check=lambda: ReadinessReport(
                database="ok",
                artifact_store="ok",
                log_directory="ok",
            )
        )
    )


def test_analysis_capability_is_false_without_llm_configuration(
    monkeypatch,
    tmp_path: Path,
) -> None:  # type: ignore[no-untyped-def]
    _configure_base_runtime(monkeypatch, tmp_path)

    response = _app().get("/api/v1/content-analysis-capabilities")

    assert response.status_code == 200
    assert response.json() == {"configured": False}
    assert "api_key" not in response.text.casefold()
    assert "base_url" not in response.text.casefold()
    assert "model" not in response.text.casefold()


def test_analysis_capability_is_true_only_with_required_secret(
    monkeypatch,
    tmp_path: Path,
) -> None:  # type: ignore[no-untyped-def]
    secret_dir = _configure_base_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("AIMA_LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("AIMA_LLM_MODEL", "fixture-model")

    without_secret = _app().get("/api/v1/content-analysis-capabilities")
    assert without_secret.json() == {"configured": False}

    (secret_dir / "llm_api_key").write_text("fixture-secret\n", encoding="utf-8")
    configured = _app().get("/api/v1/content-analysis-capabilities")

    assert configured.status_code == 200
    assert configured.json() == {"configured": True}
    assert "fixture-secret" not in configured.text
    assert "llm.example" not in configured.text
    assert "fixture-model" not in configured.text


def test_analysis_capability_reads_llm_secret_from_external_secret_root(
    monkeypatch,
    tmp_path: Path,
) -> None:  # type: ignore[no-untyped-def]
    internal_secret_dir = _configure_base_runtime(monkeypatch, tmp_path)
    external_secret_dir = tmp_path / "external-secrets"
    external_secret_dir.mkdir()
    monkeypatch.setenv("AIMA_EXTERNAL_SECRET_DIR", str(external_secret_dir))
    monkeypatch.setenv("AIMA_LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("AIMA_LLM_MODEL", "fixture-model")
    (external_secret_dir / "llm_api_key").write_text("fixture-secret\n", encoding="utf-8")

    response = _app().get("/api/v1/content-analysis-capabilities")

    assert response.status_code == 200
    assert response.json() == {"configured": True}
    assert not (internal_secret_dir / "llm_api_key").exists()
    assert "fixture-secret" not in response.text
