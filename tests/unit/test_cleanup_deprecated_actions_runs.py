from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import unittest

from scripts.quality.cleanup_deprecated_actions_runs import (
    RateLimit,
    WorkflowRun,
    deletion_budget,
    delete_batch,
    discover_current_workflows,
    select_deprecated_runs,
    summarise_paths,
)


@dataclass
class _FakeDeleteResult:
    outcome: str
    remaining: int


class _FakeClient:
    """提供不访问 GitHub 的 delete/rate fixture。"""

    token_name = "fake"

    def __init__(
        self,
        *,
        initial_remaining: int,
        reset_epoch: int = 2_000_000_000,
        outcomes: list[str] | None = None,
    ) -> None:
        self.remaining = initial_remaining
        self.reset_epoch = reset_epoch
        self.outcomes = list(outcomes or [])
        self.deleted_ids: list[int] = []

    def rate_limit(self) -> RateLimit:
        """返回当前测试配额。"""
        return RateLimit(
            remaining=self.remaining,
            reset_epoch=self.reset_epoch,
        )

    def delete_run(self, run_id: int) -> tuple[str, RateLimit]:
        """消费一次配额并返回配置好的删除结果。"""
        self.deleted_ids.append(run_id)
        self.remaining -= 1
        outcome = self.outcomes.pop(0) if self.outcomes else "deleted"
        return (
            outcome,
            RateLimit(
                remaining=self.remaining,
                reset_epoch=self.reset_epoch,
            ),
        )


class CleanupDeprecatedActionsRunsTest(unittest.TestCase):
    """验证 Actions 历史清理的不可恢复删除边界。"""

    def test_discovers_only_current_workflow_files(self) -> None:
        """当前 allowlist 必须只来自 checkout 中真实 yml/yaml Workflow。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "ci.yml").write_text("name: CI\n", encoding="utf-8")
            (workflows / "release.yaml").write_text(
                "name: Release\n",
                encoding="utf-8",
            )
            (workflows / "README.md").write_text("ignore\n", encoding="utf-8")

            self.assertEqual(
                discover_current_workflows(root),
                {
                    ".github/workflows/ci.yml",
                    ".github/workflows/release.yaml",
                },
            )

    def test_selects_only_exact_paths_missing_from_current_workflows(self) -> None:
        """显示名称相同或前缀相似都不能替代 exact path 判断。"""
        current = {
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
        }
        runs = [
            WorkflowRun(
                run_id=1,
                path=".github/workflows/ci.yml",
                name="Temporary Looking Name",
                created_at="2026-09-01T00:00:00Z",
            ),
            WorkflowRun(
                run_id=2,
                path=".github/workflows/old-ci.yml",
                name="CI",
                created_at="2026-09-01T00:00:01Z",
            ),
            WorkflowRun(
                run_id=3,
                path=".github/workflows/release.yml",
                name="Release dry-run for PR #1",
                created_at="2026-09-01T00:00:02Z",
            ),
        ]

        selected = select_deprecated_runs(runs, current)

        self.assertEqual([item.run_id for item in selected], [2])

    def test_summary_groups_by_path_not_display_name(self) -> None:
        """同一路径的多个历史名称仍属于一个删除边界。"""
        summary = summarise_paths(
            [
                WorkflowRun(
                    run_id=1,
                    path=".github/workflows/old.yml",
                    name="Old A",
                    created_at="2026-09-01T00:00:00Z",
                ),
                WorkflowRun(
                    run_id=2,
                    path=".github/workflows/old.yml",
                    name="Old B",
                    created_at="2026-09-02T00:00:00Z",
                ),
            ]
        )

        self.assertEqual(
            summary,
            [
                {
                    "path": ".github/workflows/old.yml",
                    "count": 2,
                    "names": ["Old A", "Old B"],
                    "oldest": "2026-09-01T00:00:00Z",
                    "latest": "2026-09-02T00:00:00Z",
                }
            ],
        )

    def test_deletion_budget_preserves_api_reserve(self) -> None:
        """删除预算必须为仓库其他 API 动作保留额度。"""
        self.assertEqual(
            deletion_budget(
                RateLimit(remaining=1000, reset_epoch=0),
                reserve_requests=150,
                max_deletions=4000,
            ),
            850,
        )
        self.assertEqual(
            deletion_budget(
                RateLimit(remaining=100, reset_epoch=0),
                reserve_requests=150,
                max_deletions=4000,
            ),
            0,
        )

    def test_delete_batch_is_idempotent_for_missing_runs(self) -> None:
        """404 等价的 missing outcome 计入已清理，不要求重复删除。"""
        runs = [
            WorkflowRun(
                run_id=1,
                path=".github/workflows/old.yml",
                name="Old",
                created_at="2026-09-01T00:00:00Z",
            ),
            WorkflowRun(
                run_id=2,
                path=".github/workflows/old.yml",
                name="Old",
                created_at="2026-09-01T00:00:01Z",
            ),
        ]
        client = _FakeClient(
            initial_remaining=500,
            outcomes=["missing", "deleted"],
        )

        result = delete_batch(
            runs,
            client,
            reserve_requests=150,
            max_deletions=4000,
        )

        self.assertEqual(client.deleted_ids, [1, 2])
        self.assertEqual(result["already_missing"], 1)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["remaining"], 0)

    def test_delete_batch_stops_before_reserved_requests(self) -> None:
        """批量删除不得把 token 配额消耗到保留阈值以下。"""
        runs = [
            WorkflowRun(
                run_id=index,
                path=".github/workflows/old.yml",
                name="Old",
                created_at=f"2026-09-01T00:00:{index:02d}Z",
            )
            for index in range(1, 6)
        ]
        client = _FakeClient(initial_remaining=153)

        result = delete_batch(
            runs,
            client,
            reserve_requests=150,
            max_deletions=4000,
        )

        self.assertEqual(client.deleted_ids, [1, 2, 3])
        self.assertEqual(result["deleted"], 3)
        self.assertEqual(result["remaining"], 2)
        self.assertEqual(result["rate_remaining"], 150)


if __name__ == "__main__":
    unittest.main()
