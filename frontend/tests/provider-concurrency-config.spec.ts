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
  it('keeps concurrency and rate controls while hiding implementation terminology', async () => {
    const html = await renderLlmPanel()

    expect(html).toContain('同时请求数上限')
    expect(html).toContain('max="5000"')
    expect(html).toContain('每秒请求启动上限')
    expect(html).toContain('自动安排任务分片')
    expect(html).toContain('结果校验失败重试次数')
    expect(html).not.toContain('Shard Size')
  })
})
