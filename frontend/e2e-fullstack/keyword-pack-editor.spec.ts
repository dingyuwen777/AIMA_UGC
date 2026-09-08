import { expect, test } from '@playwright/test'

test('词包共用表单通过单次请求完整保存草稿并从真实 API 重读', async ({ page, request }) => {
  const name = `词包统一编辑 ${Date.now()}`
  await page.goto('/collection-strategy')
  await page.getByRole('button', { name: '关键词包', exact: true }).click()
  await page.getByRole('button', { name: '新建词包', exact: true }).click()
  const create = page.getByRole('dialog', { name: '新建关键词包' })
  await create.getByLabel('词包名称', { exact: true }).fill(name)
  await create.getByLabel('描述', { exact: true }).fill('统一草稿')
  await create.getByLabel('关键词（每行一个）').fill(`${name} 一\n${name} 二`)
  const createResponse = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/v1/keyword-packs')
  await create.getByRole('button', { name: '保存词包' }).click()
  const response = await createResponse
  expect(response.status()).toBe(201)
  const pack = await response.json() as { id: string }
  await expect(create).toBeHidden()
  await page.locator('.pack-row').filter({ hasText: name }).getByRole('button', { name: '停用', exact: true }).click()
  await expect(page.locator('.pack-row').filter({ hasText: name }).getByRole('button', { name: '启用', exact: true })).toBeVisible()
  await page.locator('.detail-card').getByRole('button', { name: '编辑', exact: true }).click()
  const editor = page.getByRole('dialog', { name: '编辑关键词包' })
  await editor.getByLabel('词包名称', { exact: true }).fill(`${name} 更新`)
  await editor.getByLabel('描述', { exact: true }).fill('元数据与全部成员一起保存')
  await editor.getByRole('textbox', { name: '关键词 1', exact: true }).fill(`${name} 修改`)
  const first = editor.locator('.keyword-row').first()
  await first.getByText('平台、优先级与备注', { exact: true }).click()
  await first.getByLabel('适用平台', { exact: true }).selectOption('douyin')
  await first.getByLabel('优先级', { exact: true }).fill('11')
  await first.getByLabel('启用该关键词', { exact: true }).uncheck()
  await first.getByLabel('备注', { exact: true }).fill('完整保留备注')
  await editor.getByRole('button', { name: '移除关键词 2', exact: true }).click()
  await editor.getByLabel('关键词（每行一个）').fill(`${name} 追加`)
  const writes: string[] = []
  page.on('request', (request) => { if (request.method() !== 'GET' && request.url().includes('/keyword-packs/')) writes.push(new URL(request.url()).pathname) })
  const updateResponse = page.waitForResponse((response) => response.request().method() === 'PUT' && new URL(response.url()).pathname === `/api/v1/keyword-packs/${pack.id}`)
  await editor.getByRole('button', { name: '保存词包' }).click()
  expect((await updateResponse).status()).toBe(200)
  await expect(editor).toBeHidden()
  expect(writes).toEqual([`/api/v1/keyword-packs/${pack.id}`])
  const persistedResponse = await request.get(`/api/v1/keyword-packs/${pack.id}`)
  expect(persistedResponse.status()).toBe(200)
  const persisted = await persistedResponse.json() as { name: string; description: string; keywords: { text: string; platform_scope: string; priority: number; enabled: boolean; note: string }[] }
  expect(persisted.name).toBe(`${name} 更新`)
  expect(persisted.description).toBe('元数据与全部成员一起保存')
  expect(persisted.keywords).toHaveLength(2)
  expect(persisted.keywords).toEqual(expect.arrayContaining([
    expect.objectContaining({ text: `${name} 修改`, platform_scope: 'douyin', priority: 11, enabled: false, note: '完整保留备注' }),
    expect.objectContaining({ text: `${name} 追加`, platform_scope: 'all', priority: 100, enabled: true }),
  ]))
})
