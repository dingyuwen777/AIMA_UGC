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
  it('keeps vehicle, pack relation, atomic scheme and audit in one guarded page', async () => {
    const html = await renderPage()

    for (const label of ['车型目录', '词包车型关联', 'Analysis Scheme', '审计记录']) {
      expect(html).toContain(label)
    }
    expect(html).toContain('有引用的车型仅允许停用、改名或合并')
    expect(html).toContain('所有修改、发布和回滚均写入审计')
    expect(html).not.toContain('双人审批')
  })
})
