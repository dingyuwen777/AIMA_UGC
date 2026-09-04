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
  it('exposes provider concurrency and RPS without exposing a shard-size input', async () => {
    const html = await renderLlmPanel()

    expect(html).toContain('模型并发上限')
    expect(html).toContain('max="5000"')
    expect(html).toContain('最大 RPS')
    expect(html).toContain('自动计算 Shard Size')
    expect(html).toContain('最大校验重试次数')
    expect(html).not.toContain('Shard Size</span><input')
  })
})
