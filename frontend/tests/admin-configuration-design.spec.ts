import { renderToString } from '@vue/server-renderer'
import { createPinia } from 'pinia'
import { createSSRApp, defineComponent, h } from 'vue'
import { describe, expect, it } from 'vitest'

import AdminConfigurationPage from '../src/features/admin-configuration/pages/AdminConfigurationPage.vue'
import { useIdentityStore } from '../src/features/identity/store'

async function renderPage(): Promise<string> {
  const app = createSSRApp({ render: () => h(AdminConfigurationPage) })
  const pinia = createPinia()
  app.use(pinia)
  useIdentityStore(pinia).principal = {
    principal_id: 'local-administrator',
    display_name: '本地管理员',
    role: 'administrator',
    source: 'development',
    is_administrator: true,
  }
  app.component(
    'RouterLink',
    defineComponent({
      props: { to: { type: String, required: true } },
      setup(props, { slots }) {
        return () => h('a', { href: props.to }, slots.default?.())
      },
    }),
  )
  return renderToString(app)
}

describe('administrator configuration baseline', () => {
  it('keeps all administrator capabilities while presenting business-readable navigation', async () => {
    const html = await renderPage()

    for (const label of [
      '车型管理',
      '词包关联',
      'AI 模型',
      'TikHub',
      'AI 分析原则',
      '操作记录',
    ]) {
      expect(html).toContain(label)
    }
    expect(html).toContain('车型编码创建后保持不变')
    expect(html).toContain('技术标识与原始审计数据仅在需要时展开查看')
    expect(html).not.toContain('Analysis Scheme')
    expect(html).not.toContain('审计记录')
    expect(html).not.toContain('双人审批')
  })
})
