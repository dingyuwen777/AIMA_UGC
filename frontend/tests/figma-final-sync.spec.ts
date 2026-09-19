import { readFile } from 'node:fs/promises'

import { describe, expect, it } from 'vitest'

describe('Figma 与前端最终交互同步', () => {
  it('详情抽屉保留正式 Figma 的四段导航与滚动实现', async () => {
    const source = await readFile(
      new URL('../src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue', import.meta.url),
      'utf8',
    )

    expect(source).toContain('aria-label="详情快捷导航"')
    expect(source).toContain("{ key: 'content', label: '内容' }")
    expect(source).toContain("{ key: 'analysis', label: 'AI 信息' }")
    expect(source).toContain("{ key: 'manual', label: '人工确认' }")
    expect(source).toContain("{ key: 'comments', label: '评论' }")
    expect(source).toContain("scrollIntoView({ behavior: 'smooth', block: 'start' })")
  })

  it('管理员页把未保存状态收敛到统一的 Tab 离开确认', async () => {
    const source = await readFile(
      new URL('../src/features/admin-configuration/pages/AdminConfigurationPage.vue', import.meta.url),
      'utf8',
    )

    expect(source).toContain("const currentDirty = ref(false)")
    expect(source).toContain("const pendingTab = ref<Tab | null>(null)")
    expect(source).toContain('if (currentDirty.value)')
    expect(source).toContain('放弃未保存的修改？')
    expect(source).toContain('继续编辑')
    expect(source).toContain('放弃修改并切换')
    expect(source).toContain('@dirty-change="handleDirtyChange"')
  })
})
