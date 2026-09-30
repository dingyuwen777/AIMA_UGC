import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import { describe, expect, it } from 'vitest'

import AnalysisLabelsEditor from '../src/features/admin-configuration/components/AnalysisLabelsEditor.vue'

interface PromptTaxonomyPayload {
  labels: Record<string, string[]>
}

function currentPromptLabels(): Record<string, string[]> {
  const path = fileURLToPath(new URL(
    '../../backend/src/aima_ugc/modules/analysis/prompts/content_labeling.md',
    import.meta.url,
  ))
  const prompt = readFileSync(path, 'utf8')
  const match = prompt.match(
    /<!-- AIMA_TAXONOMY_START -->\s*```json\s*([\s\S]*?)\s*```\s*<!-- AIMA_TAXONOMY_END -->/,
  )
  if (!match?.[1]) throw new Error('当前 content_labeling.md 缺少可解析的 Taxonomy 区块')
  return (JSON.parse(match[1]) as PromptTaxonomyPayload).labels
}

describe('AnalysisLabelsEditor', () => {
  it('按当前 Prompt 原样显示一级和二级标签，不注入旧兜底标签', async () => {
    const labels = currentPromptLabels()
    const modelValue = JSON.stringify(labels, null, 2)
    const updates: string[] = []
    const html = await renderToString(createSSRApp(AnalysisLabelsEditor, {
      modelValue,
      'onUpdate:modelValue': (value: string) => updates.push(value),
    }))

    const renderedPrimaryCount = html.match(/aria-label="一级标签名称"/g)?.length ?? 0
    const renderedSecondaryCount = html.match(/aria-label="二级标签 \d+"/g)?.length ?? 0
    for (const [primary, secondaries] of Object.entries(labels)) {
      expect(html).toContain(`value="${primary}"`)
      for (const secondary of secondaries) expect(html).toContain(`value="${secondary}"`)
    }
    expect(renderedPrimaryCount).toBe(9)
    expect(renderedSecondaryCount).toBe(39)
    expect(html).not.toContain('无法分类')
    expect(html).not.toContain('无法判断')
    expect(updates).toEqual([])
  })
})
