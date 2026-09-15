from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
RELEASE_CORE = ROOT / "scripts" / "release" / "release_bundle.py"


def _workflow_text() -> str:
    assert RELEASE_WORKFLOW.is_file()
    return RELEASE_WORKFLOW.read_text(encoding="utf-8")


def _core_text() -> str:
    assert RELEASE_CORE.is_file()
    return RELEASE_CORE.read_text(encoding="utf-8")


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
    assert "sudo -E python3 scripts/release/release_bundle.py build" in build_job
    assert "--source-profile official" in build_job
    assert "--builder-context github-actions" in build_job
    assert "--verify" in build_job
    assert "--strict-replay" in build_job
    assert 'sudo chown -R "$(id -u):$(id -g)" release-bundle' in build_job
    assert 'sudo chown "$(id -u):$(id -g)" "${CANDIDATE_ARCHIVE}"' in build_job

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


def test_release_candidate_uses_shared_bundle_core_and_internal_tool_artifact() -> None:
    workflow = _workflow_text()
    build_job = workflow.split("publish-release:", 1)[0]
    publish_job = _publish_job(workflow)

    assert "scripts/release/release_bundle.py build" in build_job
    assert "Prepare compressed release candidate transfer" in build_job
    assert "scripts/release/release_bundle.py" in build_job.split(
        "Prepare compressed release candidate transfer", 1
    )[1]
    assert "path: release-candidate" in publish_job
    assert 'RELEASE_TOOL="release-candidate/scripts/release/release_bundle.py"' in publish_job
    assert 'BUNDLE_DIR="release-candidate/release-bundle"' in publish_job
    assert 'python3 "${RELEASE_TOOL}" finalize' in publish_job


def test_release_candidate_cross_job_transfer_uses_precompressed_archive() -> None:
    workflow = _workflow_text()
    build_job = workflow.split("publish-release:", 1)[0]
    publish_job = _publish_job(workflow)

    transfer_block = build_job.split("Prepare compressed release candidate transfer", 1)[1].split(
        "Upload replay-tested release candidate", 1
    )[0]
    upload_block = build_job.split("Upload replay-tested release candidate", 1)[1].split(
        "Report dry-run result", 1
    )[0]
    verification = publish_job.split("Verify transferred candidate", 1)[1].split(
        "Load and tag exact replay-tested images", 1
    )[0]

    assert 'CANDIDATE_ARCHIVE="${RUNNER_TEMP}/AIMA_UGC-${VERSION}-deploy.tar.gz"' in transfer_block
    assert 'cp "${CANDIDATE_ARCHIVE}" "${TRANSFER_DIR}/candidate.tar.gz"' in transfer_block
    assert (
        'cp scripts/release/release_bundle.py "${TRANSFER_DIR}/scripts/release/release_bundle.py"'
        in transfer_block
    )
    assert 'gzip -t "${TRANSFER_DIR}/candidate.tar.gz"' in transfer_block
    assert "path: release-transfer/" in upload_block
    assert "release-bundle/" not in upload_block
    assert "compression-level: 0" in upload_block

    assert 'TRANSFER_ARCHIVE="release-candidate/candidate.tar.gz"' in verification
    assert 'gzip -t "${TRANSFER_ARCHIVE}"' in verification
    assert 'tar -xzf "${TRANSFER_ARCHIVE}" -C "${BUNDLE_DIR}"' in verification
    assert 'test -s "${BUNDLE_DIR}/images.tar"' in verification


def test_public_repository_release_keeps_downloadable_offline_images() -> None:
    workflow = _workflow_text()
    core = _core_text()
    publish_job = _publish_job(workflow)
    bundle_builder = core.split("def build_bundle_files(", 1)[1].split("def _find_free_port(", 1)[0]

    # 正式 GitHub Release 仍附带完整离线部署包；Bundle 生成由共享核心负责。
    assert '"docker",' in bundle_builder
    assert '"save",' in bundle_builder
    assert 'str(bundle_dir / "images.tar")' in bundle_builder
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
    core = _core_text()

    # Release 只改变镜像交付方式，不建立第二套服务器 Runtime。
    assert 'shutil.copy2(root / "compose.yaml", bundle_dir / "compose.yaml")' in core
    assert '"docker", "load", "-i"' in core
    assert '"--no-build", "--pull", "never", "--wait"' in core
    assert "docker compose --env-file env.production up -d --no-build --pull never --wait" in core
    build_step = workflow.split("Build replay-tested Linux AMD64 release bundle", 1)[1].split(
        "Upload replay-tested release candidate", 1
    )[0]
    assert "compose.windows.yaml" not in build_step
    assert "compose.windows.yaml" in core  # 只用于 Windows 本地 smoke overlay，不进入 Bundle。


def test_publish_job_uses_explicit_repository_context_without_checkout() -> None:
    publish_job = _publish_job(_workflow_text())

    # Publish 只消费 replay-tested artifact；共享工具也随候选 artifact 传递，不需要源码 checkout。
    assert "actions/checkout@" not in publish_job
    assert "GH_REPO: ${{ github.repository }}" in publish_job
    assert 'gh repo view "${GH_REPO}"' in publish_job
    assert 'gh release view "${VERSION}" --repo "${GH_REPO}"' in publish_job
    assert '--repo "${GH_REPO}"' in publish_job.split("Create Git tag and GitHub Release", 1)[1]
    assert (
        '--repo "${GH_REPO}"'
        in publish_job.split("Upload assets to published GitHub Release", 1)[1]
    )


def test_publish_job_revalidates_candidate_identity_before_external_writes() -> None:
    publish_job = _publish_job(_workflow_text())
    verification = publish_job.split("Verify transferred candidate", 1)[1].split(
        "Load and tag exact replay-tested images", 1
    )[0]

    assert '--expected-version "${VERSION}"' in verification
    assert '--expected-git-sha "${RELEASE_SHA}"' in verification
    assert "--expected-profile official" in verification
    assert "--require-offline-replay" in verification
    assert "--require-strict-replay" in verification


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
