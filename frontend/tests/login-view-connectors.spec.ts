import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * LoginView 只从 vue-router 取 `route.query`。
 *
 * 这里替换掉整个 `vue-router` 模块、用一个可变对象喂查询串：比搭一整套真实 router
 * 更贴近被测对象（少一层与本任务无关的中间状态），也让"URL 上到底带了什么"一目了然。
 */
const routeState = vi.hoisted(() => ({ query: {} as Record<string, string | undefined> }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeState.query }),
}))

import LoginView from '../src/views/LoginView.vue'

/** 两个可登录企业：顺序与后端配置顺序一致（先 nnit，后爱玛）。 */
const TWO_CONNECTORS = [
  { code: 'nnit', display_name: 'NNIT' },
  { code: 'aima', display_name: '爱玛科技' },
]

/** 模拟 `/api/v1/auth/connectors` 正常返回企业列表。 */
function connectorsOk(items: unknown[]) {
  const mock = vi.fn(async () =>
    new Response(JSON.stringify({ items }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', mock)
  return mock
}

/** 模拟滚动升级期间仍在运行的旧后端：端点尚未注册，返回 404。 */
function connectorsMissing() {
  const mock = vi.fn(async () => new Response('{"detail":"Not Found"}', { status: 404 }))
  vi.stubGlobal('fetch', mock)
  return mock
}

/** 模拟网络层直接失败（断网、URL 解析失败等）。 */
function connectorsThrows() {
  const mock = vi.fn(async () => {
    throw new TypeError('fetch failed')
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

/**
 * 用 SSR 渲染登录页。
 *
 * 项目没有安装 jsdom/happy-dom，不能做 DOM 挂载；沿用既有 `app-shell-identity.spec.ts`
 * 的做法，用 SSR 输出 HTML 来断言"页面上看得见什么"。
 */
async function renderLogin(): Promise<string> {
  const app = createSSRApp({ render: () => h(LoginView) })
  app.use(createPinia())
  return renderToString(app)
}

/** 去掉 SSR 在 `v-if` 分支边界插入的注释，避免断言绑死在实现细节上。 */
function plain(html: string): string {
  return html.replace(/<!--[\s\S]*?-->/g, '')
}

beforeEach(() => {
  routeState.query = {}
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('登录页：多企业自动路由', () => {
  it('有 ?c=aima：显示"你正在从【爱玛科技】登录"，且登录链接带上 connector=aima', async () => {
    routeState.query = { c: 'aima' }
    const fetchMock = connectorsOk(TWO_CONNECTORS)

    const html = await renderLogin()

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/connectors', expect.anything())
    expect(plain(html)).toContain('你正在从【爱玛科技】登录')
    expect(html).toContain('href="/api/v1/auth/feishu/login?connector=aima"')
  })

  it('有 ?c=aima：不再展示企业列表（已经定位到企业，不必再选一次）', async () => {
    routeState.query = { c: 'aima' }
    connectorsOk(TWO_CONNECTORS)

    const html = await renderLogin()

    expect(plain(html)).not.toContain('请选择您的企业')
    expect(html).not.toContain('href="/api/v1/auth/feishu/login?connector=nnit"')
  })

  it('无 ?c= 且多企业：按配置顺序展示企业列表', async () => {
    connectorsOk(TWO_CONNECTORS)

    const html = await renderLogin()
    expect(plain(html)).toContain('请选择您的企业')
    expect(html).toContain('href="/api/v1/auth/feishu/login?connector=nnit"')
    expect(html).toContain('href="/api/v1/auth/feishu/login?connector=aima"')
    expect(plain(html)).toContain('NNIT')
    expect(plain(html)).toContain('爱玛科技')
    // 多企业时不该再出现"通用单按钮"，否则用户会分不清自己进的是哪家。
    expect(plain(html)).not.toContain('飞书登录')
    // 顺序必须跟随后端返回顺序，不能前端自行排序。
    expect(html.indexOf('connector=nnit')).toBeLessThan(html.indexOf('connector=aima'))
  })

  it('无 ?c= + 单企业：渲染结果与改造前逐字一致', async () => {
    connectorsOk([{ code: 'aima', display_name: '爱玛科技' }])

    const html = await renderLogin()

    expect(html).toBe(
      '<div class="login-page" data-v-45f5edd7><div class="login-card" data-v-45f5edd7>'
      + LEGACY_CARD_HTML,
    )
  })

  it('旧后端接口 404：降级为单个「飞书登录」按钮，链接不带 connector', async () => {
    connectorsMissing()

    const html = await renderLogin()

    expect(html).toContain(LEGACY_ACTION_HTML)
    expect(plain(html)).not.toContain('请选择您的企业')
  })

  it('接口返回 0 家企业：同样降级为单个按钮', async () => {
    connectorsOk([])

    const html = await renderLogin()

    expect(html).toContain(LEGACY_ACTION_HTML)
    expect(plain(html)).not.toContain('请选择您的企业')
  })

  it('接口网络失败：登录页照常可用，降级为单个按钮', async () => {
    connectorsThrows()

    const html = await renderLogin()

    expect(html).toContain(LEGACY_ACTION_HTML)
    expect(plain(html)).not.toContain('请选择您的企业')
  })

  it('?c= 指向不存在的企业：降级为通用文案（不空白、也不显示别家名字）', async () => {
    routeState.query = { c: 'ghost' }
    connectorsOk(TWO_CONNECTORS)

    const html = await renderLogin()

    expect(plain(html)).toContain('请使用企业飞书账号登录。')
    expect(plain(html)).not.toContain('你正在从')
    expect(plain(html)).not.toContain('请选择您的企业')
    expect(plain(html)).not.toContain('爱玛科技')
  })

  it('保留 return_to，并与 connector 同时传给后端', async () => {
    routeState.query = { c: 'aima', return_to: '/voice-plaza' }
    connectorsOk(TWO_CONNECTORS)

    const html = await renderLogin()

    expect(html).toContain('return_to=%2Fvoice-plaza')
    expect(html).toContain('connector=aima')
  })

  it('列表里形状不完整的条目被忽略，不会渲染成空按钮', async () => {
    routeState.query = {}
    connectorsOk([{ code: 'aima', display_name: '爱玛科技' }, { code: 'broken' }, { display_name: '无名' }])

    const html = await renderLogin()

    // 只剩 1 条有效条目 → 仍按"单企业"降级，不显示列表。
    expect(plain(html)).not.toContain('请选择您的企业')
    expect(html).toContain(LEGACY_ACTION_HTML)
  })
})

/**
 * 改造前（单企业）渲染出来的「提示语 + 登录按钮」片段。
 * 兼容性红线：单企业 + 无 `?c=` 时这一串必须逐字保持。
 */
const LEGACY_ACTION_HTML =
  '<p class="hint" data-v-45f5edd7> 请使用企业飞书账号登录。 </p>'
  + '<a class="login-action" href="/api/v1/auth/feishu/login" data-v-45f5edd7>飞书登录</a>'

/**
 * 改造前整张卡片的 HTML（改造前实测采集，`<!---->` 是 SSR 在 `v-if` 处留下的空注释）。
 * 用 `toBe` 整串比对而不是 `toContain`：只有整串一致才能证明"单企业形态没有多出任何东西"。
 */
const LEGACY_CARD_HTML =
  '<h1 data-v-45f5edd7>爱玛用户声音</h1>'
  + '<p class="subtitle" data-v-45f5edd7> 智能监测与洞察平台 </p>'
  + LEGACY_ACTION_HTML
  + '<!----></div></div>'
