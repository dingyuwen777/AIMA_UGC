from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _workflow_text() -> str:
    assert RELEASE_WORKFLOW.is_file()
    return RELEASE_WORKFLOW.read_text(encoding="utf-8")


def _publish_job(workflow: str) -> str:
    assert "publish-release:" in workflow
    return workflow.split("publish-release:", 1)[1]


def test_formal_release_is_manual_and_pr_mode_is_dry_run_only() -> None:
    workflow = _workflow_text()
    header, jobs = workflow.split("jobs:", 1)

    assert "workflow_dispatch:" in header
    assert "pull_request:" in header
    assert "push:" not in header
    assert "permissions:\n  contents: read" in header

    publish_job = _publish_job(jobs)
    assert "if: github.event_name == 'workflow_dispatch'" in publish_job
    assert "contents: write" in publish_job
    assert "packages: write" in publish_job


def test_release_fails_closed_unless_both_ghcr_packages_are_private() -> None:
    workflow = _workflow_text()
    publish_job = _publish_job(workflow)

    assert "packages: read" in workflow.split("publish-release:", 1)[0]
    assert "Verify GHCR packages are private" in workflow
    assert "Revalidate private GHCR packages before push" in publish_job
    assert '"/users/${PACKAGE_OWNER}/packages/container/${package_name}"' in workflow
    assert '[[ "${visibility}" != "private" ]]' in workflow
    assert "refuse to publish a non-private GHCR package" in workflow
    assert "Change visibility" not in workflow


def test_public_repository_release_keeps_downloadable_offline_images() -> None:
    workflow = _workflow_text()
    publish_job = _publish_job(workflow)

    # 当前源码仓库是 public；用户明确要求正式 GitHub Release 仍附带完整离线部署包。
    # GHCR application packages 保持 private，但 Release asset 中的 images.tar 会随 public
    # GitHub Release 对外可下载，这是已确认的交付边界。
    assert "docker save -o release-bundle/images.tar" in workflow
    assert 'DEPLOY_ARCHIVE="AIMA_UGC-${VERSION}-deploy.tar.gz"' in publish_job
    release_create = publish_job.split("gh release create", 1)[1]
    assert '"${DEPLOY_ARCHIVE}"' in release_create
    assert "Verify published GitHub Release" in publish_job
    assert '"${DEPLOY_ARCHIVE}"' in publish_job.split("Verify published GitHub Release", 1)[1]


def test_offline_release_preserves_server_compose_start_command() -> None:
    workflow = _workflow_text()

    # Release 只改变镜像交付方式，不建立第二套服务器 Runtime。
    # docker load 后继续运行 canonical compose.yaml 与现有 env.production。
    assert "cp compose.yaml release-bundle/compose.yaml" in workflow
    assert "docker load -i images.tar" in workflow
    assert (
        "docker compose --env-file env.production up -d --no-build --pull never --wait"
        in workflow
    )
    assert "compose.windows.yaml" not in workflow


def test_publish_job_uses_explicit_repository_context_without_checkout() -> None:
    publish_job = _publish_job(_workflow_text())

    # Publish consumes the replay-tested artifact; it must not need a source checkout
    # merely so GitHub CLI can infer which repository to operate on.
    assert "actions/checkout@" not in publish_job
    assert "GH_REPO: ${{ github.repository }}" in publish_job
    assert 'gh repo view "${GH_REPO}"' in publish_job
    assert 'gh release view "${VERSION}" --repo "${GH_REPO}"' in publish_job
    assert '--repo "${GH_REPO}"' in publish_job.split("gh release create", 1)[1]


def test_publish_job_verifies_the_created_release_and_assets() -> None:
    publish_job = _publish_job(_workflow_text())

    assert "Verify published GitHub Release" in publish_job
    assert 'gh release view "${VERSION}" --repo "${GH_REPO}"' in publish_job
    for asset in (
        "release-manifest.json",
        "migration-manifest.json",
        "SHA256SUMS",
        '"${DEPLOY_ARCHIVE}"',
    ):
        assert asset in publish_job
