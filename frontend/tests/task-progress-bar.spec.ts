import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'

import TaskProgressBar from '../src/shared/TaskProgressBar.vue'

describe('TaskProgressBar', () => {
  it('renders a clamped determinate value with accessible progress semantics', async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(TaskProgressBar, {
        label: '迁移进度',
        value: 125,
        detail: '100 / 101 行',
      }),
    }))

    expect(html).toContain('role="progressbar"')
    expect(html).toContain('aria-label="迁移进度"')
    expect(html).toContain('aria-valuenow="100"')
    expect(html).toContain('100%')
    expect(html).toContain('100 / 101 行')
  })

  it('omits a made-up percentage for indeterminate work', async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(TaskProgressBar, {
        label: '发现文件',
        indeterminate: true,
        detail: '正在枚举批准目录',
      }),
    }))

    expect(html).not.toContain('aria-valuenow')
    expect(html).not.toMatch(/\d+%/)
    expect(html).toContain('正在枚举批准目录')
  })
})
