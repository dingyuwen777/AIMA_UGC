import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const componentPath = fileURLToPath(new URL(
  '../src/features/admin-configuration/pages/AdminConfigurationPage/components/AnalysisSchemePanel.vue',
  import.meta.url,
))

describe('analysis scheme prompt display', () => {
  it('binds the active database Scheme prompt template to the advanced editor', () => {
    const source = readFileSync(componentPath, 'utf8')

    expect(source).toContain('promptTemplate: version.definition.prompt_template')
    expect(source).toContain('v-model="schemeDraft.promptTemplate"')
    expect(source).toContain('selectSchemeVersion(initial.id)')
  })
})
