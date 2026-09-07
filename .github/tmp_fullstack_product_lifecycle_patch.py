from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, got {count}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


stage12 = Path('frontend/e2e-fullstack/stage12-historical-analysis.spec.ts')
text = stage12.read_text(encoding='utf-8')
helper_anchor = """async function injectPrewriteChunkFailure(campaignId: string): Promise<void> {\n  await execFileAsync(\n    'uv',\n    [\n      'run',\n      'python',\n      'tests/fullstack/force_stage12_ready_chunk_failed.py',\n      campaignId,\n    ],\n    {\n      cwd: resolve(process.cwd(), '..'),\n      env: { ...process.env, AIMA_FULLSTACK_SEED: '1' },\n    },\n  )\n}\n"""
helper_addition = """

async function revokeHistoricalCampaign(
  page: Page,
  request: APIRequestContext,
  campaignId: string,
): Promise<void> {
  await page.goto(`/collection-runtime?data_import_campaign_id=${campaignId}`)
  const dialog = page.getByRole('dialog', { name: '导入数据' })
  await expect(dialog).toBeVisible({ timeout: 60_000 })

  const previewResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'GET'
      && new URL(response.url()).pathname
        === `/api/v1/data-import-campaigns/${campaignId}/revocation-preview`,
  )
  await dialog.getByRole('button', { name: '评估撤销', exact: true }).click()
  const previewResponse = await previewResponsePromise
  expect(previewResponse.status()).toBe(200)
  const preview = await previewResponse.json() as {
    eligible: boolean
    already_revoked: boolean
    impact: {
      affected_content_count: number
      hidden_content_count: number
      retained_shared_content_count: number
      unreversible_content_count: number
    }
  }
  expect(preview.eligible).toBe(true)
  expect(preview.already_revoked).toBe(false)
  expect(preview.impact.affected_content_count).toBeGreaterThan(0)
  expect(preview.impact.hidden_content_count).toBeGreaterThan(0)
  expect(preview.impact.retained_shared_content_count).toBeGreaterThan(0)
  expect(preview.impact.unreversible_content_count).toBe(0)
  await expect(dialog.getByText('撤销影响', { exact: true })).toBeVisible()
  await expect(dialog.getByText('其它来源保留', { exact: true })).toBeVisible()

  page.once('dialog', (confirmation) => confirmation.accept())
  const revokeResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST'
      && new URL(response.url()).pathname === `/api/v1/data-import-campaigns/${campaignId}/revoke`,
  )
  await dialog.getByRole('button', { name: '撤销本次导入', exact: true }).click()
  const revokeResponse = await revokeResponsePromise
  expect(revokeResponse.status()).toBe(200)
  const revoked = await revokeResponse.json() as {
    already_revoked: boolean
    impact: {
      affected_content_count: number
      hidden_content_count: number
      retained_shared_content_count: number
    }
  }
  expect(revoked.already_revoked).toBe(false)
  expect(revoked.impact).toMatchObject({
    affected_content_count: preview.impact.affected_content_count,
    hidden_content_count: preview.impact.hidden_content_count,
    retained_shared_content_count: preview.impact.retained_shared_content_count,
  })
  await expect(dialog.getByText(/撤销完成：影响 \d+ 条内容/)).toBeVisible()

  const repeated = await request.post(`/api/v1/data-import-campaigns/${campaignId}/revoke`, {
    data: { reason: 'full-stack idempotency check' },
  })
  expect(repeated.status()).toBe(200)
  expect((await repeated.json() as { already_revoked: boolean }).already_revoked).toBe(true)

  const hiddenResponse = await request.get(
    `/api/v1/contents?search=${encodeURIComponent('爱玛 Stage12 历史新建')}&limit=10`,
  )
  expect(hiddenResponse.status()).toBe(200)
  const hiddenItems = await hiddenResponse.json() as { items: Array<{ title: string | null }> }
  expect(hiddenItems.items.some((item) => item.title === '爱玛 Stage12 历史新建')).toBe(false)

  const retainedResponse = await request.get(
    `/api/v1/contents?search=${encodeURIComponent('爱玛 Stage12 当前标题')}&limit=10`,
  )
  expect(retainedResponse.status()).toBe(200)
  const retainedItems = await retainedResponse.json() as { items: Array<{ title: string | null }> }
  expect(retainedItems.items.some((item) => item.title === '爱玛 Stage12 当前标题')).toBe(true)

  await page.goto('/voice-plaza')
  await expect(page.getByText('爱玛 Stage12 当前标题', { exact: true })).toBeVisible()
  await expect(page.getByText('爱玛 Stage12 历史新建', { exact: true })).toHaveCount(0)
}
"""
if helper_addition.strip() not in text:
    if text.count(helper_anchor) != 1:
        raise RuntimeError(f'stage12 helper anchor count={text.count(helper_anchor)}')
    text = text.replace(helper_anchor, helper_anchor + helper_addition, 1)

tail_old = """  const allRun = await createAllDataAnalysisRun(page, request)\n  expect(allRun.id).not.toBe(firstRun.id)\n  expect(allRun.id).not.toBe(secondRun.id)\n  expect(allRun.sequenceNo).toBeGreaterThan(secondRun.sequenceNo)\n  expect(allRun.targetCount).toBeGreaterThan(1)\n})\n"""
tail_new = """  const allRun = await createAllDataAnalysisRun(page, request)\n  expect(allRun.id).not.toBe(firstRun.id)\n  expect(allRun.id).not.toBe(secondRun.id)\n  expect(allRun.sequenceNo).toBeGreaterThan(secondRun.sequenceNo)\n  expect(allRun.targetCount).toBeGreaterThan(1)\n\n  await revokeHistoricalCampaign(page, request, campaignId)\n})\n"""
if text.count(tail_old) != 1:
    raise RuntimeError(f'stage12 tail anchor count={text.count(tail_old)}')
text = text.replace(tail_old, tail_new, 1)
stage12.write_text(text, encoding='utf-8')

admin = Path('frontend/e2e-fullstack/admin-product-capabilities.spec.ts')
text = admin.read_text(encoding='utf-8')
replacements = [
    ("page.getByText('车型已创建并写入审计。', { exact: true })", "page.getByText('车型已创建并记录操作。', { exact: true })", 'vehicle notice'),
    ("page.getByRole('button', { name: '词包车型关联', exact: true })", "page.getByRole('button', { name: '词包关联', exact: true })", 'pack link tab first'),
    ("page.getByText('词包与车型关联已更新并写入审计。', { exact: true })", "page.getByText('词包与车型关联已更新并记录操作。', { exact: true })", 'pack notice'),
    ("page.getByRole('button', { name: '词包车型关联', exact: true })", "page.getByRole('button', { name: '词包关联', exact: true })", 'pack link tab second'),
    ("page.getByRole('button', { name: '审计记录', exact: true })", "page.getByRole('button', { name: '操作记录', exact: true })", 'audit tab first'),
    ("  const auditRow = page.getByRole('row').filter({ hasText: code })\n  await expect(auditRow).toContainText('vehicle_model_created')\n  await expect(auditRow).toContainText('local-administrator')", "  const auditRow = page.getByRole('row').filter({ hasText: '新增车型' }).first()\n  await expect(auditRow).toContainText('车型')\n  await expect(auditRow).toContainText('local-administrator')\n  await expect(auditRow).not.toContainText('vehicle_model_created')", 'audit business projection'),
    ("  await expect(vehicleEvidence.getByText(`import · “${alias}” · catalog v`, { exact: false })).toBeVisible()", "  await expect(vehicleEvidence).toContainText('系统识别')\n  await expect(vehicleEvidence).toContainText(`命中“${alias}”`)\n  await expect(vehicleEvidence).not.toContainText('catalog v')", 'vehicle evidence projection'),
    ("page.getByRole('button', { name: 'Analysis Scheme', exact: true })", "page.getByRole('button', { name: 'AI 分析规则', exact: true })", 'analysis tab'),
    ("name: new RegExp(`v${activeBefore!.version} · published`),", "name: new RegExp(`版本 ${activeBefore!.version} · 已发布`),", 'version label'),
    ("page.getByText('Analysis Scheme 草稿已保存并写入审计。', { exact: true })", "page.getByText('AI 分析规则草稿已保存并记录操作。', { exact: true })", 'scheme draft notice'),
    ("page.getByText('Analysis Scheme 已发布并写入审计。', { exact: true })", "page.getByText('AI 分析规则已发布并记录操作。', { exact: true })", 'scheme publish notice'),
    ("page.getByRole('button', { name: '审计记录', exact: true })", "page.getByRole('button', { name: '操作记录', exact: true })", 'audit tab second'),
]
for old, new, label in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, got {count}')
    text = text.replace(old, new, 1)

new_test = """

test('未引用关键词包可以从业务界面归档、恢复并安全永久删除', async ({ page, request }) => {
  const pack = await createKeywordPack(request, `lifecycle-${Date.now()}`)

  await page.goto('/collection-strategy')
  let packRow = page.locator('.pack-row').filter({ hasText: pack.name })
  await expect(packRow).toBeVisible()
  await packRow.click()

  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '归档', exact: true }).click()
  await expect(page.getByText('词包已归档。', { exact: true })).toBeVisible()
  await expect(page.locator('.pack-row').filter({ hasText: pack.name })).toHaveCount(0)

  const archivedDetails = page.locator('details.archived-card')
  if (!await archivedDetails.evaluate((element) => (element as HTMLDetailsElement).open)) {
    await archivedDetails.locator('summary').click()
  }
  let archivedRow = archivedDetails.locator('.archived-row').filter({ hasText: pack.name })
  await expect(archivedRow).toBeVisible()
  await archivedRow.getByRole('button', { name: '恢复', exact: true }).click()
  await expect(page.getByText('词包已恢复，当前保持停用。', { exact: true })).toBeVisible()

  packRow = page.locator('.pack-row').filter({ hasText: pack.name })
  await expect(packRow).toBeVisible()
  await expect(packRow).toContainText('已停用')
  await packRow.click()

  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '归档', exact: true }).click()
  await expect(page.getByText('词包已归档。', { exact: true })).toBeVisible()
  archivedRow = archivedDetails.locator('.archived-row').filter({ hasText: pack.name })
  await expect(archivedRow).toBeVisible()

  page.once('dialog', (dialog) => dialog.accept())
  await archivedRow.getByRole('button', { name: '永久删除', exact: true }).click()
  await expect(page.getByText('未被业务引用的归档词包已永久删除。', { exact: true })).toBeVisible()
  await expect(archivedDetails.locator('.archived-row').filter({ hasText: pack.name })).toHaveCount(0)

  const deleted = await request.get(`/api/v1/keyword-packs/${pack.id}`)
  expect(deleted.status()).toBe(404)
})
"""
if "test('未引用关键词包可以从业务界面归档、恢复并安全永久删除'" not in text:
    text = text.rstrip() + new_test + '\n'
admin.write_text(text, encoding='utf-8')
