import { readFile } from 'node:fs/promises'

import { describe, expect, it } from 'vitest'

const runtimeRoot = new URL(
  '../src/features/import-batches/pages/CollectionRuntimePage/',
  import.meta.url,
)
const sharedUiRoot = new URL('../src/shared/ui/', import.meta.url)
const ownerGuide = new URL(
  '../../docs/guides/07_采集运行中心Figma开发基线.md',
  import.meta.url,
)

/** 读取采集运行中心页面或组件源码，用于锁定 Figma 正式基线的结构性约束。 */
async function readRuntimeSource(relativePath: string): Promise<string> {
  return readFile(new URL(relativePath, runtimeRoot), 'utf8')
}

/** 读取跨页面共享 UI Owner，避免业务页面重新拼装第二套 Overlay/空状态外壳。 */
async function readSharedUiSource(filename: string): Promise<string> {
  return readFile(new URL(filename, sharedUiRoot), 'utf8')
}

describe('采集运行中心 release-2 Figma 基线', () => {
  it('默认筛选只展示搜索、日期、状态与类型，不暴露内部处理阶段', async () => {
    const source = await readRuntimeSource('components/CollectionRuntimeFilters.vue')

    expect(source).toContain('placeholder="搜索任务名称或来源文件"')
    expect(source).toContain('按任务名称、创建时间、状态和类型筛选')
    expect(source).not.toContain("defineModel<string>('stage'")
    expect(source).not.toContain('aria-label="处理阶段"')
    expect(source).not.toContain('runtimeStageLabel')
  })

  it('在 1120px 及以下按 Figma 紧凑规范稳定切换为两列筛选', async () => {
    const source = await readRuntimeSource('components/CollectionRuntimeFilters.vue')

    expect(source).toContain('@media (max-width: 1120px)')
    expect(source).toContain('grid-template-columns: repeat(2, minmax(0, 1fr))')
    expect(source).toContain('@media (max-width: 720px)')
    expect(source).toContain('grid-template-columns: minmax(0, 1fr)')
  })

  it('长期基线记录 Figma 四层 Owner、正式页面和响应式锚点', async () => {
    const source = await readFile(ownerGuide, 'utf8')

    for (const owner of ['L1', 'L2', 'L3', 'L4']) expect(source).toContain(`| ${owner} |`)
    for (const node of ['7840:9761', '3500:2025', '4742:2404', '4742:2603']) {
      expect(source).toContain(`\`${node}\``)
    }
    expect(source).toContain('frontend/src/shared/ui/')
    expect(source).toContain('CollectionRuntimePage/components/')
  })

  it('主列表使用 1212px 七列产品表格与 Figma 状态进度组件', async () => {
    const [tableSource, statusSource] = await Promise.all([
      readRuntimeSource('components/CollectionRuntimeTable.vue'),
      readRuntimeSource('components/CollectionRuntimeStatusProgress.vue'),
    ])

    expect(tableSource).toContain('<span>处理环节</span>')
    expect(tableSource).toContain('min-width: 1212px')
    expect(tableSource).toContain('<CollectionRuntimeStatusProgress')
    expect(tableSource).not.toContain('<span>{{ elapsed(')
    expect(statusSource).toContain('status-pill')
    expect(statusSource).toContain('status-progress')
    expect(statusSource).toContain('partial_success')
  })

  it('运行记录覆盖 Loading、Empty、Error/Retry 三种产品状态', async () => {
    const source = await readRuntimeSource('components/CollectionRuntimeTable.vue')

    expect(source).toContain('正在读取采集运行…')
    expect(source).toContain('<AimaEmptyState')
    expect(source).toContain('采集运行加载失败，请稍后重试。')
    expect(source).toContain("$emit('retry')")
  })

  it('复杂 Overlay 复用共享 Drawer/Modal Shell，业务内容仍留在 Feature', async () => {
    const [drawerShell, modalShell, emptyState, importDetail, runDetail, supplement, dataImport] = await Promise.all([
      readSharedUiSource('AimaDrawer.vue'),
      readSharedUiSource('AimaModalContainer.vue'),
      readSharedUiSource('AimaEmptyState.vue'),
      readRuntimeSource('components/ImportBatchDetailDrawer.vue'),
      readRuntimeSource('components/CollectionRunDetailDrawer.vue'),
      readRuntimeSource('components/TikHubSupplementDrawer.vue'),
      readRuntimeSource('components/DataImportDialog.vue'),
    ])

    expect(drawerShell).toContain('class="aima-drawer"')
    expect(drawerShell).toMatch(/<slot\s+name="header"/)
    expect(drawerShell).toMatch(/<slot\s+name="footer"/)
    expect(modalShell).toContain('class="aima-modal-container"')
    expect(emptyState).toContain('class="aima-empty-state"')
    expect(importDetail).toContain('<AimaDrawer')
    expect(runDetail).toContain('<AimaDrawer')
    expect(supplement).toContain('<AimaDrawer')
    expect(dataImport).toContain('<AimaModalContainer')
  })

  it('批次详情使用 Figma 的产品标题与四个详情页签', async () => {
    const source = await readRuntimeSource('components/ImportBatchDetailDrawer.vue')

    expect(source).toContain('批次详情')
    expect(source).toContain("label: '运行概览'")
    expect(source).toContain("label: '执行进度'")
    expect(source).toContain("label: '任务信息'")
    expect(source).toContain("label: '问题记录'")
  })
})
