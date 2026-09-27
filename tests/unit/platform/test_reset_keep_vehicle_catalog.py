from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest


SCRIPT_SOURCE = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "deploy"
    / "reset_keep_vehicle_catalog.sh"
)
POSIX_BASH_ONLY = pytest.mark.skipif(
    os.name != "posix" or shutil.which("bash") is None,
    reason="该部署脚本只在 POSIX Bash 环境验证",
)


def _write_fake_runtime(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """准备只在临时目录内生效的 Docker/psql 假运行时。"""

    repo_root = tmp_path / "repo"
    script_dir = repo_root / "scripts" / "deploy"
    script_dir.mkdir(parents=True)
    script = script_dir / "reset_keep_vehicle_catalog.sh"
    script.write_text(
        SCRIPT_SOURCE.read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )
    (repo_root / "compose.yaml").write_text("name: test\n", encoding="utf-8")

    env_file = tmp_path / "env.production"
    env_file.write_text("AIMA_HOST_ROOT=/unused\n", encoding="utf-8")
    data_root = tmp_path / "runtime" / "data"
    (data_root / "artifacts").mkdir(parents=True)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    fingerprint_calls = tmp_path / "fingerprint_calls.txt"

    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import sys

            args = sys.argv[1:]
            with open(
                os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8"
            ) as handle:
                handle.write(" ".join(args) + "\\n")
            if args == ["info"]:
                raise SystemExit(0)
            if not args or args[0] != "compose":
                raise SystemExit(2)

            rest = args[1:]
            if len(rest) >= 2 and rest[0] == "--env-file":
                rest = rest[2:]
            if rest == ["ps", "-q", "postgres"]:
                print("fake-postgres")
                raise SystemExit(0)
            if rest == ["config", "--format", "json"]:
                print(
                    json.dumps(
                        {
                            "services": {
                                "worker": {
                                    "volumes": [
                                        {
                                            "source": os.environ["FAKE_DATA_ROOT"],
                                            "target": "/app/data",
                                            "type": "bind",
                                        }
                                    ]
                                }
                            }
                        }
                    )
                )
                raise SystemExit(0)
            if rest and rest[0] == "stop":
                raise SystemExit(0)

            if len(rest) >= 5 and rest[:4] == ["exec", "-T", "postgres", "sh"]:
                command = rest[5] if len(rest) > 5 else ""
                if "pg_dump" in command:
                    print("-- fake vehicle catalog dump")
                    raise SystemExit(0)

                sql = sys.stdin.read()
                if "WITH keep(name)" in sql:
                    print("")
                elif "n.nspname NOT IN ('public'" in sql:
                    print("")
                elif "JOIN pg_depend d" in sql:
                    print("")
                elif (
                    "string_agg(version_num" in sql
                    and "count(*) FROM vehicle_catalog_versions" in sql
                ):
                    print("8|3|6|0|0|20260922_0057")
                elif "current_database()" in sql:
                    print("aima_ugc|aima_ugc")
                elif "count(*) = 1 FROM alembic_version" in sql:
                    print("t")
                elif "md5(COALESCE" in sql:
                    counter_path = os.environ["FAKE_FINGERPRINT_CALLS"]
                    try:
                        count = int(
                            open(counter_path, encoding="utf-8").read()
                        )
                    except (FileNotFoundError, ValueError):
                        count = 0
                    with open(counter_path, "w", encoding="utf-8") as handle:
                        handle.write(str(count + 1))
                    with open(
                        os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8"
                    ) as handle:
                        handle.write(f"FINGERPRINT {count + 1}\\n")
                    if count == 0:
                        print(
                            os.environ.get(
                                "FAKE_PRE_FINGERPRINT",
                                "fp1|fp2|fp3|fp4|fp5",
                            )
                        )
                    elif count == 1:
                        print(
                            os.environ.get(
                                "FAKE_BASELINE_FINGERPRINT",
                                "fp1|fp2|fp3|fp4|fp5",
                            )
                        )
                    else:
                        print(
                            os.environ.get(
                                "FAKE_AFTER_FINGERPRINT",
                                os.environ.get(
                                    "FAKE_BASELINE_FINGERPRINT",
                                    "fp1|fp2|fp3|fp4|fp5",
                                ),
                            )
                        )
                elif (
                    "SELECT c.relname FROM pg_class" in sql
                    and "c.relname<>ALL" in sql
                ):
                    print("contents")
                    print("jobs")
                elif "BEGIN;" in sql:
                    print("")
                elif "voice_plaza_projection_state WHERE singleton" in sql:
                    print("1")
                elif "SELECT (SELECT count(*) FROM collection_runs)" in sql:
                    print("0|0|0|0|0|0|0")
                else:
                    print("")
                raise SystemExit(0)

            raise SystemExit(3)
            """
        ),
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    fake_findmnt = fake_bin / "findmnt"
    fake_findmnt.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    fake_findmnt.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["FAKE_DATA_ROOT"] = str(data_root)
    env["FAKE_DOCKER_LOG"] = str(docker_log)
    env["FAKE_FINGERPRINT_CALLS"] = str(fingerprint_calls)
    return script, env_file, env


@POSIX_BASH_ONLY
def test_reset_keep_vehicle_catalog_dry_run_accepts_brand_only_catalog(
    tmp_path: Path,
) -> None:
    """只有品牌、没有车型时，dry-run 仍应安全通过且不停止容器。"""

    script, env_file, env = _write_fake_runtime(tmp_path)

    result = subprocess.run(
        ["bash", str(script), "--env-file", str(env_file), "--dry-run"],
        cwd=script.parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "8|3|6|0|0|20260922_0057" in result.stdout
    assert "目录为空也是合法状态" in result.stdout
    assert "dry-run 完成；未停止容器、未修改数据库或文件。" in result.stdout
    calls = Path(env["FAKE_DOCKER_LOG"]).read_text(encoding="utf-8").splitlines()
    assert not any(" stop " in f" {line} " for line in calls)
    assert "--allow-empty-catalog" not in script.read_text(encoding="utf-8")


@POSIX_BASH_ONLY
def test_reset_keep_vehicle_catalog_execute_preserves_catalog_fingerprint(
    tmp_path: Path,
) -> None:
    """隔离执行路径应备份目录、清 Artifact，并保持目录内容指纹不变。"""

    script, env_file, env = _write_fake_runtime(tmp_path)
    artifact = Path(env["FAKE_DATA_ROOT"]) / "artifacts" / "stale.bin"
    artifact.write_bytes(b"stale")

    result = subprocess.run(
        [
            "bash",
            str(script),
            "--env-file",
            str(env_file),
            "--execute",
            "--yes",
        ],
        cwd=script.parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "品牌/车型目录与 Alembic 版本保持不变" in result.stdout
    assert not artifact.exists()
    backups = list((tmp_path / "backups").glob("vehicle_catalog_*.sql.gz"))
    assert len(backups) == 1
    assert backups[0].stat().st_size > 0
    calls = Path(env["FAKE_DOCKER_LOG"]).read_text(encoding="utf-8").splitlines()
    stop_index = next(
        index
        for index, line in enumerate(calls)
        if " stop frontend api worker scheduler configure migrate" in line
    )
    baseline_index = calls.index("FINGERPRINT 2")
    assert stop_index < baseline_index


@POSIX_BASH_ONLY
def test_reset_keep_vehicle_catalog_execute_uses_post_stop_catalog_baseline(
    tmp_path: Path,
) -> None:
    """停写窗口内目录变化时，应以停止写入后的目录状态作为最终保留基线。"""

    script, env_file, env = _write_fake_runtime(tmp_path)
    env["FAKE_PRE_FINGERPRINT"] = "before-stop"
    env["FAKE_BASELINE_FINGERPRINT"] = "after-stop"
    env["FAKE_AFTER_FINGERPRINT"] = "after-stop"

    result = subprocess.run(
        [
            "bash",
            str(script),
            "--env-file",
            str(env_file),
            "--execute",
            "--yes",
        ],
        cwd=script.parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "停写后保留目录计数" in result.stdout


@POSIX_BASH_ONLY
def test_reset_keep_vehicle_catalog_execute_fails_if_catalog_content_changes(
    tmp_path: Path,
) -> None:
    """目录内容指纹变化时必须 fail closed，不能继续报告重置成功。"""

    script, env_file, env = _write_fake_runtime(tmp_path)
    env["FAKE_AFTER_FINGERPRINT"] = "changed|fingerprint"

    result = subprocess.run(
        [
            "bash",
            str(script),
            "--env-file",
            str(env_file),
            "--execute",
            "--yes",
        ],
        cwd=script.parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "清空后品牌/车型目录内容发生变化" in result.stderr
