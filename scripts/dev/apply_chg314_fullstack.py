"""一次性升级 CHG-314 的真实 Full-stack Golden Path。"""

from __future__ import annotations

from apply_chg314 import ROOT, replace_once


def patch_atomic_pack_helper(path: str, function_name: str) -> None:
    old = '''  const created = await request.post('/api/v1/keyword-packs', { data: { name } })
  expect(created.status()).toBe(201)
  const pack = await created.json() as { id: string }
  const keyword = await request.post(`/api/v1/keyword-packs/${pack.id}/keywords`, {
    data: { text: '爱玛', priority: 10 },
  })
  expect(keyword.status()).toBe(201)
  return { id: pack.id, name }
'''
    new = '''  const created = await request.post('/api/v1/keyword-packs', {
    data: {
      name,
      keywords: [{ text: '爱玛', priority: 10, enabled: true }],
    },
  })
  expect(created.status()).toBe(201)
  const pack = await created.json() as { id: string; keywords: { text: string }[] }
  expect(pack.keywords.map((item) => item.text)).toEqual(['爱玛'])
  return { id: pack.id, name }
'''
    replace_once(path, old, new)


def append_real_audit_pagination() -> None:
    path = ROOT / "frontend/e2e-fullstack/admin-product-capabilities.spec.ts"
    text = path.read_text(encoding="utf-8")
    marker = "真实审计历史翻到第二页"
    if marker in text:
        raise RuntimeError("audit pagination full-stack test already exists")
    text += '''

test('真实审计历史翻到第二页', async ({ page, request }) => {
  const suffix = Date.now().toString()
  for (let index = 0; index < 105; index += 1) {
    const response = await request.post('/api/v1/keyword-packs', {
      data: { name: `audit-page-${suffix}-${index}` },
    })
    expect(response.status()).toBe(201)
  }

  await page.goto('/admin/configuration')
  await page.getByRole('button', { name: '审计记录', exact: true }).click()
  const secondPageRequest = page.waitForRequest((candidate) => {
    const url = new URL(candidate.url())
    return url.pathname === '/api/v1/audit-events' && url.searchParams.get('offset') === '100'
  })
  await page.getByRole('button', { name: '下一页', exact: true }).click()
  await secondPageRequest
  await expect(page.getByText(/第 2 \/ \d+ 页/)).toBeVisible()
})
'''
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_atomic_pack_helper(
        "frontend/e2e-fullstack/admin-product-capabilities.spec.ts",
        "admin-product",
    )
    patch_atomic_pack_helper(
        "frontend/e2e-fullstack/stage12-historical-analysis.spec.ts",
        "stage12",
    )
    append_real_audit_pagination()


if __name__ == "__main__":
    main()
