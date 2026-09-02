"""一次性修复 CHG-314 Browser Mock fail-closed 首轮暴露的测试归属问题。"""

from __future__ import annotations

from apply_chg314 import replace_once


def main() -> None:
    # 两个旧 spec 的局部 catch-all 只能处理本 spec 业务 API；共享 Shell API 交回全局 fixture。
    for path in (
        "frontend/e2e/collection-runtime.spec.ts",
        "frontend/e2e/excel-import-submit-state.spec.ts",
    ):
        replace_once(
            path,
            "    await route.fulfill({ status: 404, body: 'not mocked' })\n",
            "    await route.fallback()\n",
        )

    # 新功能用例以分页整句做严格定位，避免 Header 和 Pager 的合法重复总数文案触发 strict-mode。
    replace_once(
        "frontend/e2e/frontend-reliability.spec.ts",
        "  await expect(page.getByText('共 150 条')).toBeVisible()\n",
        "  await expect(page.getByText('第 1 / 2 页 · 共 150 条', { exact: true })).toBeVisible()\n",
    )


if __name__ == "__main__":
    main()
