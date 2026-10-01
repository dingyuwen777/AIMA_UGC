import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h } from 'vue'
import { describe, expect, it } from 'vitest'

import ProviderConfigurationPanel from '../src/features/admin-configuration/components/ProviderConfigurationPanel.vue'

async function renderLlmPanel(): Promise<string> {
  const app = createSSRApp({
    render: () => h(ProviderConfigurationPanel, { providerKind: 'llm' }),
  })
  return renderToString(app)
}

describe('LLM provider concurrency configuration', () => {
  it('shows automatic LLM execution status without manual execution controls', async () => {
    const html = await renderLlmPanel()

    expect(html).toContain('自动执行状态')
    expect(html).toContain('成功入库速度')
    expect(html).not.toContain('同时请求数上限')
    expect(html).not.toContain('每秒请求启动上限')
    expect(html).not.toContain('结果校验失败重试次数')
    expect(html).not.toContain('Shard Size')
  })

  it('preserves collection execution controls', async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(ProviderConfigurationPanel, { providerKind: 'collection' }),
    }))
    expect(html).toContain('同时请求数上限')
    expect(html).toContain('每秒请求启动上限')
    expect(html).toContain('请求失败重试次数')
    expect(html).not.toContain('自动执行状态')
  })
})
