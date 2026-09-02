import { createSSRApp, defineComponent, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'

import AppShell from '../src/app/layouts/AppShell.vue'
import { useIdentityStore } from '../src/features/identity/store'

async function renderShell(role: 'administrator' | 'user' = 'user'): Promise<string> {
  const routerLink = defineComponent({
    props: {
      to: { type: String, required: true },
    },
    setup(props, { slots }) {
      return () => h('a', { href: props.to }, slots.default?.())
    },
  })
  const app = createSSRApp({ render: () => h(AppShell) })
  const pinia = createPinia()
  app.use(pinia)
  useIdentityStore(pinia).principal = {
    principal_id: role === 'administrator' ? 'local-administrator' : 'ordinary-user',
    display_name: role === 'administrator' ? '本地管理员' : '普通用户',
    role,
    source: 'development',
    is_administrator: role === 'administrator',
  }
  app.component('RouterLink', routerLink)
  return renderToString(app)
}

describe('AppShell 内网 V1 导航', () => {
  it('首页和三个首版业务页面都是可导航入口', async () => {
    const html = await renderShell()

    expect(html).toContain('href="/"')
    expect(html).toContain('首页')
    expect(html).toContain('href="/voice-plaza"')
    expect(html).toContain('声音广场')
    expect(html).toContain('href="/collection-runtime"')
    expect(html).toContain('采集运行中心')
    expect(html).toContain('href="/collection-strategy"')
    expect(html).toContain('采集策略')
  })

  it('不把尚未实现的未来能力显示成无效菜单项', async () => {
    const html = await renderShell()

    for (const label of ['智能洞察', '销售漏斗', '热点捕捉', '管理员页面', '帮助与反馈']) {
      expect(html).not.toContain(label)
    }
  })

  it('只向管理员展示独立配置入口', async () => {
    const ordinary = await renderShell('user')
    const administrator = await renderShell('administrator')

    expect(ordinary).not.toContain('href="/admin/configuration"')
    expect(administrator).toContain('href="/admin/configuration"')
    expect(administrator).toContain('管理员配置')
  })

  it('使用代码内 SVG 图标且页面壳尺寸对齐正式桌面基线', async () => {
    const html = await renderShell()

    expect(html).toContain('data-aima-icon="home"')
    expect(html).toContain('data-aima-icon="strategy"')
    expect(html).not.toMatch(/[⌂◌▣◎♧⚙]/u)
    expect(html).toContain('智能监测与洞察平台')
  })
})
