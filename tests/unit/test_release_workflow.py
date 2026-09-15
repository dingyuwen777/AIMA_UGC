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
    assert "release:" in header
    assert "published" in header
    assert "create:" not in header
    assert "push:" not in header
    assert 'VERSION="${{ github.event.release.tag_name }}"' in jobs
    assert "pull_request:" in header
    assert "ready_for_review" in header
    assert "permissions:\n  contents: read" in header

    build_job = jobs.split("publish-release:", 1)[0]
    assert (
        "github.event_name != 'pull_request' || github.event.pull_request.draft == false"
        in build_job
    )
    assert "ref: ${{ github.event_name == 'pull_request' && github.sha || 'main' }}" in build_job

    publish_job = _publish_job(jobs)
    assert "github.event_name == 'workflow_dispatch'" in publish_job
    assert "github.event_name == 'release'" in publish_job
    assert "contents: write" in publish_job
    assert "packages: write" in publish_job


def test_formal_release_can_inherit_only_guarded_archive_evidence() -> None:
    workflow = _workflow_text()

    assert "Resolve required main CI evidence" in workflow
    assert "scripts/quality/release_evidence.py resolve" in workflow
    assert "scripts/quality/release_evidence.py verify" in workflow
    assert "steps.ci_evidence.outputs.evidence_sha" in workflow


def test_published_release_requires_latest_main_and_exact_tag_target() -> None:
    workflow = _workflow_text()
    formal_validation = workflow.split("Validate formal release request", 1)[1].split(
        "Verify GHCR packages are private", 1
    )[0]
    publish_validation = _publish_job(workflow).split(
        "Revalidate private GHCR packages before push", 1
    )[0]

    assert '"${GITHUB_EVENT_NAME}" == "release"' in formal_validation
    assert '"${GITHUB_REF}" != "refs/tags/${VERSION}"' in formal_validation
    assert '"/repos/${GH_REPO}/git/ref/heads/main"' in formal_validation
    assert "--jq '.object.sha'" in formal_validation
    assert '"${CURRENT_MAIN_SHA}" != "${RELEASE_SHA}"' in formal_validation
    assert "git fetch --no-tags --depth=1 origin main" not in formal_validation
    assert '"/repos/${GH_REPO}/commits/${VERSION}"' in formal_validation
    assert '"${TAG_TARGET}" != "${RELEASE_SHA}"' in formal_validation
    assert "Release 发布事件要求 Git Tag" in formal_validation
    assert '"/repos/${GH_REPO}/releases/tags/${VERSION}"' in formal_validation
    assert "Release 发布事件要求 GitHub Release" in formal_validation
    assert "Actions 手工发布要求版本尚未存在 GitHub Release" in formal_validation

    assert '"${CURRENT_MAIN_SHA}" != "${RELEASE_SHA}"' in publish_validation
    assert '"${TAG_TARGET}" != "${RELEASE_SHA}"' in publish_validation
    assert "Release 发布阶段要求 Git Tag" in publish_validation
    assert '"/repos/${GH_REPO}/releases/tags/${VERSION}"' in publish_validation
    assert "Release 发布阶段要求 GitHub Release" in publish_validation
    assert "Actions 手工发布阶段发现同名 GitHub Release 已存在" in publish_validation
    assert "git update-ref" not in workflow
    assert "git tag -f" not in workflow
    assert "--force" not in formal_validation


def test_release_publication_splits_create_and_upload_paths() -> None:
    publish_job = _publish_job(_workflow_text())

    create_step = publish_job.split("Create Git tag and GitHub Release", 1)[1].split(
        "Upload assets to published GitHub Release", 1
    )[0]
    upload_step = publish_job.split("Upload assets to published GitHub Release", 1)[1].split(
        "Verify published GitHub Release", 1
    )[0]

    assert "if: github.event_name == 'workflow_dispatch'" in create_step
    assert 'gh release create "${VERSION}"' in create_step
    assert '--target "${RELEASE_SHA}"' in create_step
    assert "if: github.event_name == 'release'" in upload_step
    assert 'gh release upload "${VERSION}"' in upload_step
    assert '"${DEPLOY_ARCHIVE}"' in upload_step
    assert "--clobber" not in upload_step


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

    # 当前源码仓库是 public；正式 GitHub Release 仍附带完整离线部署包。
    # GHCR application packages 保持 private，但 Release asset 中的 images.tar 会随 public
    # GitHub Release 对外可下载，这是已确认的交付边界。
    assert "docker save -o release-bundle/images.tar" in workflow
    assert 'DEPLOY_ARCHIVE="AIMA_UGC-${VERSION}-deploy.tar.gz"' in publish_job
    assert '"${DEPLOY_ARCHIVE}"' in publish_job.split("Create Git tag and GitHub Release", 1)[1]
    assert (
        '"${DEPLOY_ARCHIVE}"'
        in publish_job.split("Upload assets to published GitHub Release", 1)[1]
    )
    assert "Verify published GitHub Release" in publish_job
    assert '"${DEPLOY_ARCHIVE}"' in publish_job.split("Verify published GitHub Release", 1)[1]


def test_offline_release_preserves_server_compose_start_command() -> None:
    workflow = _workflow_text()

    # Release 只改变镜像交付方式，不建立第二套服务器 Runtime。
    # docker load 后继续运行 canonical compose.yaml 与现有 env.production。
    assert "cp compose.yaml release-bundle/compose.yaml" in workflow
    assert "docker load -i images.tar" in workflow
    assert (
        "docker compose --env-file env.production up -d --no-build --pull never --wait" in workflow
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
    assert '--repo "${GH_REPO}"' in publish_job.split("Create Git tag and GitHub Release", 1)[1]
    assert (
        '--repo "${GH_REPO}"'
        in publish_job.split("Upload assets to published GitHub Release", 1)[1]
    )


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
