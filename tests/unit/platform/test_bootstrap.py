from aima_ugc.bootstrap.migration import create_migration_runtime
from aima_ugc.bootstrap.scheduler import create_scheduler_runtime
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.platform.config import PlatformSettings


def build_settings(tmp_path) -> PlatformSettings:
    return PlatformSettings(
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
        secret_dir=tmp_path / "secrets",
    )


def test_worker_scheduler_and_migration_share_platform_bootstrap(tmp_path) -> None:
    settings = build_settings(tmp_path)

    worker = create_worker_runtime(settings=settings)
    worker.close()
    scheduler = create_scheduler_runtime(settings=settings)
    scheduler.close()
    migration = create_migration_runtime(settings=settings)
    migration.close()

    assert (settings.log_dir / "worker.log").is_file()
    assert (settings.log_dir / "scheduler.log").is_file()
    assert not (settings.log_dir / "migrate.log").exists()
