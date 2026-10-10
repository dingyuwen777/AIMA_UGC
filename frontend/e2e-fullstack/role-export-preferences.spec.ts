import { spawn, type ChildProcess } from 'node:child_process'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test, type Browser, type BrowserContext } from '@playwright/test'

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const api = 'http://127.0.0.1:8092'
const origin = 'http://127.0.0.1:4174'
type TestAccount = { principal_id: string; token: string }
type Sessions = { cookie_name: string; admin: TestAccount; user_a: TestAccount; user_b: TestAccount }
let sessions: Sessions
let server: ChildProcess
let directory: string
let diagnostics = ''

test.beforeAll(async () => {
  test.setTimeout(120_000)
  directory = await mkdtemp(join(tmpdir(), 'aima-role-browser-'))
  const tokenFile = join(directory, 'sessions.json')
  server = spawn('uv', ['run', 'python', 'tests/fullstack/role_sessions_api.py', '--token-file', tokenFile], {
    cwd: repository,
    env: { ...process.env, AIMA_FULLSTACK_SEED: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  server.stdout?.on('data', (chunk: Buffer) => { diagnostics = (diagnostics + chunk.toString()).slice(-4000) })
  server.stderr?.on('data', (chunk: Buffer) => { diagnostics = (diagnostics + chunk.toString()).slice(-4000) })
  await expect.poll(async () => {
    if (server.exitCode !== null) throw new Error(`角色 API 启动失败：${diagnostics}`)
    try {
      const response = await fetch(`${api}/health/ready`)
      if (!response.ok) return false
      sessions = JSON.parse(await readFile(tokenFile, 'utf8')) as Sessions
      return true
    } catch { return false }
  }, { timeout: 90_000 }).toBe(true)
})

test.afterAll(async () => {
  if (server && server.exitCode === null) {
    const exited = new Promise<void>((done) => { server.once('exit', () => done()) })
    server.kill('SIGTERM')
    await Promise.race([exited, new Promise<void>((done) => setTimeout(done, 10_000))])
  }
  if (directory) await rm(directory, { recursive: true, force: true })
})

/** 只转发真实 HTTP 到隔离 Session API；响应仍来自生产 Service、PG 和 Worker。 */
async function accountContext(browser: Browser, account: TestAccount): Promise<BrowserContext> {
  const context = await browser.newContext()
  await context.addCookies([{ name: sessions.cookie_name, value: account.token, url: origin }])
  await context.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    await route.fulfill({ response: await route.fetch({ url: `${api}${url.pathname}${url.search}` }) })
  })
  return context
}

test('真实 Session 双用户的只读 UI、默认字段、导出归属和账号切换', async ({ browser }) => {
  test.setTimeout(180_000)
  const a = await accountContext(browser, sessions.user_a)
  const b = await accountContext(browser, sessions.user_b)
  const admin = await accountContext(browser, sessions.admin)
  try {
    const page = await a.newPage()
    const managementRequests: string[] = []
    page.on('request', (request) => {
      const path = new URL(request.url()).pathname
      if (/^\/api\/v1\/(analysis\/content-runs|collection-runtime)/.test(path)) managementRequests.push(path)
    })
    await page.goto(`${origin}/voice-plaza`)
    await expect(page.getByRole('navigation', { name: '业务导航' }).getByRole('link')).toHaveCount(2)
    await expect(page.getByRole('button', { name: /AI 分析/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /评论补采/ })).toHaveCount(0)
    await expect(page.getByRole('checkbox', { name: '选择当前已加载内容' })).toBeVisible()
    await page.getByRole('button', { name: '任务中心', exact: true }).click()
    await expect(page.getByRole('button', { name: '取消任务', exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: '关闭任务中心', exact: true }).last().click()
    expect(managementRequests).toEqual([])

    await page.getByRole('button', { name: '导出记录', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '导出声音记录' })
    await expect(dialog.getByLabel('正文', { exact: true })).toBeChecked()
    await expect(dialog.getByText('Raw/来源定位', { exact: true })).toHaveCount(0)
    await expect(dialog.getByText('来源项ID', { exact: true })).toHaveCount(0)
    for (const checkbox of await dialog.locator('.column-picker input[type=checkbox]').all()) await checkbox.uncheck()
    await dialog.getByLabel('标题', { exact: true }).check()
    await dialog.getByLabel('正文', { exact: true }).check()
    await dialog.getByRole('button', { name: '设为我的默认字段', exact: true }).click()
    await expect(dialog.getByText('已保存为我的默认字段。')).toBeVisible()
    const saved = await (await a.request.get(`${api}/api/v1/me/export-column-default`)).json()
    expect(saved.columns).toEqual(['title', 'text'])
    expect((await (await b.request.get(`${api}/api/v1/me/export-column-default`)).json()).columns).toBeNull()

    // 重新建立浏览器上下文，恢复服务器默认；临时字段导出不能改长期配置。
    const secondDevice = await accountContext(browser, sessions.user_a)
    try {
      const second = await secondDevice.newPage()
      await second.goto(`${origin}/voice-plaza`)
      await second.getByRole('button', { name: '导出记录', exact: true }).click()
      const secondDialog = second.getByRole('dialog', { name: '导出声音记录' })
      await expect(secondDialog.getByLabel('标题', { exact: true })).toBeChecked()
      await expect(secondDialog.getByLabel('作者', { exact: true })).not.toBeChecked()
      await secondDialog.getByLabel('作者', { exact: true }).check()
      const created = second.waitForResponse((response) => response.request().method() === 'POST' && response.url().endsWith('/api/v1/data-exports'))
      await secondDialog.getByRole('button', { name: /开始导出/ }).click()
      const accepted = await created
      expect(accepted.status()).toBe(202)
      const x = await accepted.json() as { export_id: string }
      expect((await (await a.request.get(`${api}/api/v1/me/export-column-default`)).json()).columns).toEqual(['title', 'text'])
      expect((await b.request.get(`${api}/api/v1/data-exports/${x.export_id}`)).status()).toBe(404)
      expect((await b.request.get(`${api}/api/v1/data-exports/${x.export_id}/download`)).status()).toBe(404)
      expect((await admin.request.get(`${api}/api/v1/data-exports/${x.export_id}`)).status()).toBe(200)
      await expect.poll(async () => (await (await a.request.get(`${api}/api/v1/data-exports/${x.export_id}`)).json()).job.status,
        { timeout: 60_000 }).toBe('succeeded')
      expect((await a.request.get(`${api}/api/v1/data-exports/${x.export_id}/download`)).status()).toBe(200)
      const history = await (await b.request.get(`${api}/api/v1/data-exports`)).json()
      expect(history.items.map((item: { id: string }) => item.id)).not.toContain(x.export_id)
    } finally { await secondDevice.close() }

    await dialog.getByRole('button', { name: '取消', exact: true }).click()
    await page.evaluate(() => sessionStorage.setItem('aima.voice-plaza.applied-search.v1', JSON.stringify({ filters: { search: '甲的条件' }, sortBy: 'published_at', sortDirection: 'desc' })))
    await page.reload()
    expect(await page.evaluate(() => sessionStorage.getItem('aima.voice-plaza.applied-search.v1'))).toContain('甲的条件')
    await a.addCookies([{ name: sessions.cookie_name, value: sessions.user_b.token, url: origin }])
    await page.reload()
    await expect(page.locator('.principal-name')).toContainText('全栈用户乙')
    expect(await page.evaluate(() => sessionStorage.getItem('aima.voice-plaza.applied-search.v1'))).not.toContain('甲的条件')
    await page.goto(`${origin}/collection-runtime`)
    await expect(page.getByText('当前账号无管理员权限')).toBeVisible()
    expect(managementRequests).toEqual([])
  } finally {
    await Promise.all([a.close(), b.close(), admin.close()])
  }
})
