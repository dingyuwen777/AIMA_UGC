import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type {
  BrandResponse,
  ContentAnalysisTaxonomyResponse,
  GetWorkbenchMindParams,
  GetWorkbenchStreamParams,
  GetWorkbenchTrendParams,
  PlatformName,
  VehicleModelResponse,
  WorkbenchLayoutModule,
  WorkbenchLayoutResponse,
  WorkbenchMindResponse,
  WorkbenchModuleId,
  WorkbenchStreamResponse,
  WorkbenchTrendResponse,
} from '../../generated/api/client'
import { apiErrorMessage } from '../../shared/api/http'
import {
  fetchActiveBrands,
  fetchActiveVehicleModels,
  fetchWorkbenchLayout,
  fetchWorkbenchMind,
  fetchWorkbenchStream,
  fetchWorkbenchTaxonomy,
  fetchWorkbenchTrend,
  saveWorkbenchLayout,
} from './api'

export interface WorkbenchFilters {
  dateFrom: string
  dateTo: string
  platforms: PlatformName[]
  brandIds: string[]
  vehicleModelIds: string[]
  voiceTypes: string[]
  sentiments: string[]
  primaryLabels: string[]
  secondaryLabels: string[]
}

type WorkbenchModuleKey = 'stream' | 'mind' | 'trend'
export type WorkbenchMindMetric = 'share' | 'positive'

/** 以北京时间取自然日字符串，浏览器时区不能改变工作台默认范围。 */
function beijingToday(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  return ['year', 'month', 'day']
    .map((type) => parts.find((part) => part.type === type)?.value)
    .join('-')
}

/** 使用 UTC 日历做纯日期偏移，避免宿主夏令时影响北京时间业务日。 */
function shiftDate(value: string, days: number): string {
  const date = new Date(`${value}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

/** 生成工作台默认近 30 个北京时间自然日。 */
function defaultFilters(): WorkbenchFilters {
  const dateTo = beijingToday()
  return {
    dateFrom: shiftDate(dateTo, -29),
    dateTo,
    platforms: [],
    brandIds: [],
    vehicleModelIds: [],
    voiceTypes: [],
    sentiments: [],
    primaryLabels: [],
    secondaryLabels: [],
  }
}

/** 把 UI 多选状态投影成 generated Workbench Query 参数，不复制公共 Contract 类型。 */
function queryParams(filters: WorkbenchFilters): GetWorkbenchStreamParams {
  return {
    date_from: filters.dateFrom || undefined,
    date_to: filters.dateTo || undefined,
    platforms: filters.platforms.length ? [...filters.platforms] : undefined,
    brand_ids: filters.brandIds.length ? [...filters.brandIds] : undefined,
    vehicle_model_ids: filters.vehicleModelIds.length ? [...filters.vehicleModelIds] : undefined,
    voice_types: filters.voiceTypes.length ? [...filters.voiceTypes] : undefined,
    sentiments: filters.sentiments.length ? [...filters.sentiments] : undefined,
    primary_labels: filters.primaryLabels.length ? [...filters.primaryLabels] : undefined,
    secondary_labels: filters.secondaryLabels.length ? [...filters.secondaryLabels] : undefined,
  }
}

/** active Taxonomy 切换后移除已失效的 AI 筛选值，避免隐藏旧条件把新数据筛空。 */
function sanitizeTaxonomyFilters(
  filters: WorkbenchFilters,
  taxonomy: ContentAnalysisTaxonomyResponse,
): WorkbenchFilters {
  const sentiments = new Set(taxonomy.sentiments)
  const voiceTypes = new Set(taxonomy.voice_types)
  const primaryLabels = new Set(taxonomy.labels.map((item) => item.primary_label))
  const secondaryLabels = new Set(taxonomy.labels.flatMap((item) => item.secondary_labels))
  return {
    ...filters,
    sentiments: filters.sentiments.filter((value) => sentiments.has(value)),
    voiceTypes: filters.voiceTypes.filter((value) => voiceTypes.has(value)),
    primaryLabels: filters.primaryLabels.filter((value) => primaryLabels.has(value)),
    secondaryLabels: filters.secondaryLabels.filter((value) => secondaryLabels.has(value)),
  }
}

/** 复制布局模块，编辑草稿不得与服务端已保存快照共享对象引用。 */
function cloneModules(modules: readonly WorkbenchLayoutModule[]): WorkbenchLayoutModule[] {
  return modules.map((item) => ({ ...item }))
}

/** 将布局模块按稳定 order 排序，避免服务端数组顺序成为第二套布局事实。 */
function sortedModules(modules: readonly WorkbenchLayoutModule[]): WorkbenchLayoutModule[] {
  return [...modules].sort((left, right) => left.order - right.order)
}

export const useWorkbenchStore = defineStore('workbench', () => {
  const filters = ref<WorkbenchFilters>(defaultFilters())
  const taxonomy = ref<ContentAnalysisTaxonomyResponse | null>(null)
  const brands = ref<BrandResponse[]>([])
  const vehicleModels = ref<VehicleModelResponse[]>([])
  const stream = ref<WorkbenchStreamResponse | null>(null)
  const mind = ref<WorkbenchMindResponse | null>(null)
  const trend = ref<WorkbenchTrendResponse | null>(null)
  const layout = ref<WorkbenchLayoutResponse | null>(null)
  const draftModules = ref<WorkbenchLayoutModule[]>([])
  const editing = ref(false)
  const savingLayout = ref(false)
  const loadingReference = ref(false)
  const moduleLoading = ref<Record<WorkbenchModuleKey, boolean>>({
    stream: false,
    mind: false,
    trend: false,
  })
  const moduleErrors = ref<Record<WorkbenchModuleKey, string | null>>({
    stream: null,
    mind: null,
    trend: null,
  })
  const referenceError = ref<string | null>(null)
  const globalError = ref<string | null>(null)
  const layoutError = ref<string | null>(null)
  const notice = ref<string | null>(null)
  const selectedMind = ref<string | null>(null)
  const mindMetric = ref<WorkbenchMindMetric>('share')
  let dataRevision = 0
  let referenceRevision = 0

  const primaryLabelOptions = computed(() =>
    taxonomy.value?.labels.filter((item) => item.primary_label !== '无法分类') ?? [],
  )
  const secondaryLabelOptions = computed(() =>
    primaryLabelOptions.value.flatMap((item) =>
      item.secondary_labels.map((value) => ({
        value,
        label: `${item.primary_label} / ${value}`,
      })),
    ),
  )
  const currentModules = computed(() => {
    const source = editing.value ? draftModules.value : layout.value?.modules ?? []
    return sortedModules(source)
  })
  const visibleModules = computed(() => currentModules.value.filter((item) => item.visible))
  const hiddenModules = computed(() => currentModules.value.filter((item) => !item.visible))
  const activeMind = computed(() => {
    const dimensions = mind.value?.dimensions ?? []
    return dimensions.find((item) => item.primary_label === selectedMind.value)
      ?? dimensions[0]
      ?? null
  })
  const latestAsOf = computed(() => {
    const values = [stream.value?.as_of, mind.value?.as_of, trend.value?.as_of]
      .filter((value): value is string => Boolean(value))
    if (!values.length) return null
    return values.reduce((latest, value) =>
      Date.parse(value) > Date.parse(latest) ? value : latest,
    )
  })
  const activeSchemeVersionId = computed(() =>
    trend.value?.analysis_scheme_version_id
      ?? mind.value?.analysis_scheme_version_id
      ?? stream.value?.analysis_scheme_version_id
      ?? null,
  )

  /** 读取 active Taxonomy、品牌车型目录与当前 Principal 布局；各来源独立保留错误。 */
  async function refreshReferenceData(): Promise<void> {
    const revision = ++referenceRevision
    loadingReference.value = true
    referenceError.value = null
    layoutError.value = null
    const results = await Promise.allSettled([
      fetchWorkbenchTaxonomy(),
      fetchActiveBrands(),
      fetchActiveVehicleModels(),
      fetchWorkbenchLayout(),
    ])
    if (revision !== referenceRevision) return
    const [taxonomyResult, brandResult, vehicleResult, layoutResult] = results
    const errors: string[] = []
    if (taxonomyResult.status === 'fulfilled') {
      taxonomy.value = taxonomyResult.value
      filters.value = sanitizeTaxonomyFilters(filters.value, taxonomyResult.value)
    } else errors.push(apiErrorMessage(taxonomyResult.reason))
    if (brandResult.status === 'fulfilled') brands.value = brandResult.value
    else errors.push(apiErrorMessage(brandResult.reason))
    if (vehicleResult.status === 'fulfilled') vehicleModels.value = vehicleResult.value
    else errors.push(apiErrorMessage(vehicleResult.reason))
    if (layoutResult.status === 'fulfilled') {
      layout.value = layoutResult.value
      if (!editing.value) draftModules.value = cloneModules(layoutResult.value.modules)
    } else {
      layoutError.value = apiErrorMessage(layoutResult.reason)
      errors.push(layoutError.value)
    }
    referenceError.value = errors.length ? '部分工作台筛选或布局暂不可用，可继续查看已加载模块。' : null
    loadingReference.value = false
  }

  /** 重新读取 Taxonomy，用于 active Scheme 切换后的口径同步。 */
  async function refreshTaxonomy(): Promise<void> {
    try {
      const current = await fetchWorkbenchTaxonomy()
      taxonomy.value = current
      filters.value = sanitizeTaxonomyFilters(filters.value, current)
    } catch (error) {
      referenceError.value = apiErrorMessage(error)
    }
  }

  /** 校验三个独立模块是否仍来自同一个 active Scheme Version / Taxonomy。 */
  function dataIdentityConsistent(): boolean {
    const responses = [stream.value, mind.value, trend.value].filter(
      (value): value is WorkbenchStreamResponse | WorkbenchMindResponse | WorkbenchTrendResponse =>
        value !== null,
    )
    const versions = new Set(responses.map((item) => item.analysis_scheme_version_id))
    const hashes = new Set(responses.map((item) => item.taxonomy_sha256))
    return versions.size <= 1 && hashes.size <= 1
  }

  /** 当前数据口径变化后，Taxonomy 目录必须跟随响应 hash 重新读取。 */
  async function alignTaxonomyWithData(): Promise<void> {
    const responseHash = trend.value?.taxonomy_sha256
      ?? mind.value?.taxonomy_sha256
      ?? stream.value?.taxonomy_sha256
    if (!responseHash || taxonomy.value?.taxonomy_sha256 === responseHash) return
    await refreshTaxonomy()
  }

  /** 独立刷新三个模块；单模块失败不抹掉其它模块上次成功快照。 */
  async function refreshData(silent = false, retried = false): Promise<void> {
    const revision = ++dataRevision
    globalError.value = null
    if (!silent) {
      moduleLoading.value = { stream: true, mind: true, trend: true }
    }
    const params = queryParams(filters.value)
    const results = await Promise.allSettled([
      fetchWorkbenchStream(params as GetWorkbenchStreamParams),
      fetchWorkbenchMind(params as GetWorkbenchMindParams),
      fetchWorkbenchTrend(params as GetWorkbenchTrendParams),
    ])
    if (revision !== dataRevision) return
    const [streamResult, mindResult, trendResult] = results
    if (streamResult.status === 'fulfilled') {
      stream.value = streamResult.value
      moduleErrors.value.stream = null
    } else moduleErrors.value.stream = apiErrorMessage(streamResult.reason)
    if (mindResult.status === 'fulfilled') {
      mind.value = mindResult.value
      moduleErrors.value.mind = null
    } else moduleErrors.value.mind = apiErrorMessage(mindResult.reason)
    if (trendResult.status === 'fulfilled') {
      trend.value = trendResult.value
      moduleErrors.value.trend = null
    } else moduleErrors.value.trend = apiErrorMessage(trendResult.reason)
    moduleLoading.value = { stream: false, mind: false, trend: false }

    if (!dataIdentityConsistent()) {
      globalError.value = 'Analysis Scheme 已切换，正在重新同步工作台口径。'
      if (!retried) {
        await refreshTaxonomy()
        await refreshData(true, true)
        return
      }
      globalError.value = '工作台模块暂未取得同一 Analysis Scheme Version，请稍后重试。'
      return
    }
    await alignTaxonomyWithData()
    if (mind.value?.dimensions.length) {
      if (!mind.value.dimensions.some((item) => item.primary_label === selectedMind.value)) {
        selectedMind.value = mind.value.dimensions[0]?.primary_label ?? null
      }
    } else selectedMind.value = null
  }

  /** 页面首次进入时并行准备参考数据和模块数据，首屏不等待非关键目录串行加载。 */
  async function initialize(): Promise<void> {
    await Promise.all([refreshReferenceData(), refreshData()])
  }

  /** 恢复近 30 个北京时间自然日和全维度未筛选状态。 */
  function resetFilters(): void {
    filters.value = defaultFilters()
  }

  /** 替换筛选快照；页面用 debounce 合并连续勾选后再触发查询。 */
  function setFilters(value: WorkbenchFilters): void {
    filters.value = {
      ...value,
      platforms: [...value.platforms],
      brandIds: [...value.brandIds],
      vehicleModelIds: [...value.vehicleModelIds],
      voiceTypes: [...value.voiceTypes],
      sentiments: [...value.sentiments],
      primaryLabels: [...value.primaryLabels],
      secondaryLabels: [...value.secondaryLabels],
    }
  }

  /** 进入显式布局编辑态，只创建本地草稿，不触发持久化。 */
  function startEditing(): void {
    if (!layout.value) return
    draftModules.value = cloneModules(layout.value.modules)
    editing.value = true
    layoutError.value = null
  }

  /** 取消编辑时丢弃本轮全部草稿，并恢复已保存布局。 */
  function cancelEditing(): void {
    if (layout.value) draftModules.value = cloneModules(layout.value.modules)
    editing.value = false
    layoutError.value = null
  }

  /** Drag 结束时重排草稿顺序；持久化只在 Save 时发生。 */
  function reorderModule(draggedId: WorkbenchModuleId, targetId: WorkbenchModuleId): void {
    if (!editing.value || draggedId === targetId) return
    const ordered = sortedModules(draftModules.value)
    const sourceIndex = ordered.findIndex((item) => item.module_id === draggedId)
    const targetIndex = ordered.findIndex((item) => item.module_id === targetId)
    if (sourceIndex < 0 || targetIndex < 0) return
    const [moved] = ordered.splice(sourceIndex, 1)
    if (!moved) return
    ordered.splice(targetIndex, 0, moved)
    draftModules.value = ordered.map((item, index) => ({ ...item, order: index }))
  }

  /** 编辑态显示/隐藏模块，只修改布局草稿。 */
  function setModuleVisible(moduleId: WorkbenchModuleId, visible: boolean): void {
    if (!editing.value) return
    draftModules.value = draftModules.value.map((item) =>
      item.module_id === moduleId ? { ...item, visible } : item,
    )
  }

  /** Resize 手柄把像素变化量量化到 Contract 支持的列宽与高度单位。 */
  function resizeModule(
    moduleId: WorkbenchModuleId,
    columnSpan: number,
    rowUnits: number,
  ): void {
    if (!editing.value) return
    const normalizedSpan = columnSpan >= 9 ? 12 : 6
    const normalizedRows = Math.max(48, Math.min(160, Math.round(rowUnits)))
    draftModules.value = draftModules.value.map((item) =>
      item.module_id === moduleId
        ? { ...item, column_span: normalizedSpan, row_units: normalizedRows }
        : item,
    )
  }

  /** 一次提交完整布局草稿；409 等并发错误保留草稿供用户重试或取消。 */
  async function saveLayout(): Promise<boolean> {
    if (!layout.value || savingLayout.value) return false
    savingLayout.value = true
    layoutError.value = null
    try {
      const saved = await saveWorkbenchLayout({
        revision: layout.value.revision,
        modules: sortedModules(draftModules.value),
      })
      layout.value = saved
      draftModules.value = cloneModules(saved.modules)
      editing.value = false
      notice.value = '工作台布局已保存。'
      return true
    } catch (error) {
      layoutError.value = apiErrorMessage(error)
      return false
    } finally {
      savingLayout.value = false
    }
  }

  /** 切换品牌心智主指标只改变展示，不重新请求服务端。 */
  function setMindMetric(value: WorkbenchMindMetric): void {
    mindMetric.value = value
  }

  /** 选择一个 active Taxonomy 一级心智作为右侧详情。 */
  function selectMind(primaryLabel: string): void {
    selectedMind.value = primaryLabel
  }

  /** 清理短时反馈，避免下一次成功操作仍显示旧消息。 */
  function clearNotice(): void {
    notice.value = null
  }

  return {
    filters,
    taxonomy,
    brands,
    vehicleModels,
    stream,
    mind,
    trend,
    layout,
    editing,
    savingLayout,
    loadingReference,
    moduleLoading,
    moduleErrors,
    referenceError,
    globalError,
    layoutError,
    notice,
    mindMetric,
    selectedMind,
    activeMind,
    primaryLabelOptions,
    secondaryLabelOptions,
    currentModules,
    visibleModules,
    hiddenModules,
    latestAsOf,
    activeSchemeVersionId,
    initialize,
    refreshReferenceData,
    refreshTaxonomy,
    refreshData,
    resetFilters,
    setFilters,
    startEditing,
    cancelEditing,
    reorderModule,
    setModuleVisible,
    resizeModule,
    saveLayout,
    setMindMetric,
    selectMind,
    clearNotice,
  }
})
