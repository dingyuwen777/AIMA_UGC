import { execFileSync } from 'node:child_process'
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
  const executable = fileURLToPath(new URL(
    process.platform === 'win32' ? '../../.venv/Scripts/python.exe' : '../../.venv/bin/python', import.meta.url,
  ))
  const compiled = execFileSync(executable, ['-c',
    'import json,sys; from aima_ugc.modules.analysis.prompt_taxonomy import PromptTaxonomyLoader; t=PromptTaxonomyLoader.load_text(open(sys.argv[1],encoding="utf-8").read()); print(json.dumps({"labels":dict(t.labels)},ensure_ascii=False))',
    path,
  ], { encoding: 'utf8', env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' } })
  return (JSON.parse(compiled) as PromptTaxonomyPayload).labels
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
