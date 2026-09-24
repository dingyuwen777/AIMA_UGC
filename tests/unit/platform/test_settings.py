from aima_ugc.platform.config import load_settings


def test_load_settings_uses_explicit_environment_and_resolves_paths(tmp_path) -> None:
    settings = load_settings(
        {
            "AIMA_DATA_DIR": "var/data",
            "AIMA_LOG_DIR": "var/logs",
            "AIMA_SECRET_DIR": "var/secrets",
            "AIMA_LOG_LEVEL": "DEBUG",
            "AIMA_LOG_MAX_BYTES": "1024",
            "AIMA_LOG_BACKUP_COUNT": "2",
            "AIMA_LOG_COMPRESS": "false",
            "AIMA_DB_HOST": "db.internal",
            "AIMA_DB_PORT": "5544",
            "AIMA_DB_NAME": "ugc_test",
            "AIMA_DB_USER": "ugc_user",
            "AIMA_DB_CONNECT_TIMEOUT_SECONDS": "5",
            "AIMA_UNRELATED": "ignored",
        },
        base_dir=tmp_path,
    )

    assert settings.data_dir == (tmp_path / "var/data").resolve()
    assert settings.log_dir == (tmp_path / "var/logs").resolve()
    assert settings.secret_dir == (tmp_path / "var/secrets").resolve()
    assert settings.artifact_dir == (tmp_path / "var/data/artifacts").resolve()
    assert settings.postgres_password_file == (tmp_path / "var/secrets/postgres_password").resolve()
    assert settings.log_level == "DEBUG"
    assert settings.log_max_bytes == 1024
    assert settings.log_backup_count == 2
    assert settings.log_compress is False
    assert settings.db_host == "db.internal"
    assert settings.db_port == 5544
    assert settings.db_name == "ugc_test"
    assert settings.db_user == "ugc_user"
    assert settings.db_connect_timeout_seconds == 5


def test_load_settings_defaults_are_repository_relative(tmp_path) -> None:
    settings = load_settings({}, base_dir=tmp_path)

    assert settings.data_dir == (tmp_path / ".runtime/data").resolve()
    assert settings.log_dir == (tmp_path / ".runtime/logs").resolve()
    assert settings.secret_dir == (tmp_path / ".runtime/secrets").resolve()


def test_runtime_sizing_ignores_legacy_environment_values(tmp_path) -> None:
    """历史环境值不能覆盖代码统一管理的事务与安全边界。"""

    settings = load_settings(
        {
            "AIMA_HISTORICAL_CHUNK_ROWS": "100",
            "AIMA_HISTORICAL_MAX_SCAN_FILES": "100000",
            "AIMA_HISTORICAL_MAX_DIRECTORY_DEPTH": "32",
            "AIMA_HISTORICAL_MAX_IN_FLIGHT_JOBS": "16",
            "AIMA_ANALYSIS_RUN_MAX_IN_FLIGHT_JOBS": "16",
        },
        base_dir=tmp_path,
    )

    assert settings.historical_chunk_rows == 2000
    assert settings.historical_max_scan_files == 10_000
    assert settings.historical_max_directory_depth == 8
    assert settings.historical_max_in_flight_jobs is None
    assert settings.analysis_run_max_in_flight_jobs is None
