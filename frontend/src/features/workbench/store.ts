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
import { AimaApiError, apiErrorMessage } from '../../shared/api/http'
import { useTransientNotice } from '../../shared/ui/useTransientNotice'
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

/** 聚合模块只按时间范围切片，不消费声音流的内容维度筛选。 */
export interface WorkbenchDateRange {
  dateFrom: string
  dateTo: string
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

/** 聚合模块的默认时间切片，同样取近 30 个北京时间自然日。 */
function defaultDateRange(): WorkbenchDateRange {
  const dateTo = beijingToday()
  return { dateFrom: shiftDate(dateTo, -29), dateTo }
}

/** 生成声音流默认筛选：近 30 个北京时间自然日 + 全维度未筛选。 */
function defaultFilters(): WorkbenchFilters {
  return {
    ...defaultDateRange(),
    platforms: [],
    brandIds: [],
    vehicleModelIds: [],
    voiceTypes: [],
    sentiments: [],
    primaryLabels: [],
    secondaryLabels: [],
  }
}

/** 把起止日期规范为有序闭区间，缺失端点回退到默认近 30 天。 */
function normalizeDateRange(dateFrom: string, dateTo: string): WorkbenchDateRange {
  const dates = [dateFrom, dateTo].filter(Boolean).sort()
  const fallback = defaultDateRange()
  return {
    dateFrom: dates[0] ?? fallback.dateFrom,
    dateTo: dates[1] ?? dates[0] ?? fallback.dateTo,
  }
}

/** 声音流完整筛选投影成 generated Workbench Query 参数，不复制公共 Contract 类型。 */
function streamQueryParams(filters: WorkbenchFilters): GetWorkbenchStreamParams {
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

/** 聚合模块只投影时间范围；维度筛选留给声音流。 */
function aggregateQueryParams(range: WorkbenchDateRange): { date_from?: string; date_to?: string } {
  return {
    date_from: range.dateFrom || undefined,
    date_to: range.dateTo || undefined,
  }
}

/** active Taxonomy 切换后移除已失效的 AI 筛选值，避免隐藏旧条件把新数据筛空。 */
function sanitizeTaxonomyFilters(
  filters: WorkbenchFilters,
  taxonomy: ContentAnalysisTaxonomyResponse,
): WorkbenchFilters {
  const sentiments = new Set(taxonomy.sentiments)
  const voiceTypes = new Set(taxonomy.voice_types)
  const validPrimaryLabels = new Set(taxonomy.labels.map((item) => item.primary_label))
  const primaryLabels = filters.primaryLabels.filter((value) => validPrimaryLabels.has(value))
  const selectedPrimaryLabels = new Set(primaryLabels)
  const validSecondaryLabels = new Set(
    taxonomy.labels
      .filter((item) => selectedPrimaryLabels.has(item.primary_label))
      .flatMap((item) => item.secondary_labels),
  )
  return {
    ...filters,
    sentiments: filters.sentiments.filter((value) => sentiments.has(value)),
    voiceTypes: filters.voiceTypes.filter((value) => voiceTypes.has(value)),
    primaryLabels,
    secondaryLabels: filters.secondaryLabels.filter((value) => validSecondaryLabels.has(value)),
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
  const streamFilters = ref<WorkbenchFilters>(defaultFilters())
  const mindFilters = ref<WorkbenchDateRange>(defaultDateRange())
  const trendFilters = ref<WorkbenchDateRange>(defaultDateRange())
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
  const { message: notice, show: showNotice, clear: clearNotice } = useTransientNotice()
  const selectedMind = ref<string | null>(null)
  const mindMetric = ref<WorkbenchMindMetric>('share')
  let dataRevision = 0
  let referenceRevision = 0
  const moduleRequestRevision: Record<WorkbenchModuleKey, number> = {
    stream: 0,
    mind: 0,
    trend: 0,
  }

  const primaryLabelOptions = computed(() =>
    taxonomy.value?.labels.filter((item) => item.primary_label !== '无法分类') ?? [],
  )
  const secondaryLabelOptions = computed(() => {
    const selected = new Set(streamFilters.value.primaryLabels)
    return primaryLabelOptions.value
      .filter((item) => selected.has(item.primary_label))
      .flatMap((item) =>
        item.secondary_labels.map((value) => ({
          value,
          label: `${item.primary_label} / ${value}`,
        })),
      )
  })
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
      streamFilters.value = sanitizeTaxonomyFilters(streamFilters.value, taxonomyResult.value)
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
      streamFilters.value = sanitizeTaxonomyFilters(streamFilters.value, current)
    } catch (error) {
      referenceError.value = apiErrorMessage(error)
    }
  }

  /** 提交响应前校验三个模块是否仍来自同一个 active Scheme Version / Taxonomy。 */
  function dataIdentityConsistent(
    nextStream: WorkbenchStreamResponse | null,
    nextMind: WorkbenchMindResponse | null,
    nextTrend: WorkbenchTrendResponse | null,
  ): boolean {
    const responses = [nextStream, nextMind, nextTrend].filter(
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
    if (taxonomy.value?.taxonomy_sha256 !== responseHash) {
      taxonomy.value = null
      globalError.value = '当前 Analysis Scheme 的 Taxonomy 暂未同步，请稍后重试。'
    }
  }

  /** 三个接口并发请求、各自完成即更新；慢聚合不能拖住已返回的声音流。 */
  async function refreshData(silent = false, retried = false): Promise<void> {
    const revision = ++dataRevision
    const requestRevisions: Record<WorkbenchModuleKey, number> = {
      stream: ++moduleRequestRevision.stream,
      mind: ++moduleRequestRevision.mind,
      trend: ++moduleRequestRevision.trend,
    }
    globalError.value = null
    if (!silent) {
      moduleLoading.value = { stream: true, mind: true, trend: true }
    }
    const streamParams = streamQueryParams(streamFilters.value)
    const mindParams = aggregateQueryParams(mindFilters.value)
    const trendParams = aggregateQueryParams(trendFilters.value)
    const seenIdentities = new Set<string>()
    const responseIdentity = (
      response: WorkbenchStreamResponse | WorkbenchMindResponse | WorkbenchTrendResponse,
    ): string => `${response.analysis_scheme_version_id}:${response.taxonomy_sha256}`
    const settle = async (
      key: WorkbenchModuleKey,
      request: Promise<WorkbenchStreamResponse | WorkbenchMindResponse | WorkbenchTrendResponse>,
    ): Promise<void> => {
      try {
        const response = await request
        if (revision !== dataRevision || requestRevisions[key] !== moduleRequestRevision[key]) return
        const identity = responseIdentity(response)
        seenIdentities.add(identity)
        if (key === 'stream') stream.value = response as WorkbenchStreamResponse
        else if (key === 'mind') mind.value = response as WorkbenchMindResponse
        else trend.value = response as WorkbenchTrendResponse
        // 旧快照若属于另一 Scheme，立即移除，避免显示混合口径。
        if (stream.value && responseIdentity(stream.value) !== identity) stream.value = null
        if (mind.value && responseIdentity(mind.value) !== identity) mind.value = null
        if (trend.value && responseIdentity(trend.value) !== identity) trend.value = null
        moduleErrors.value[key] = null
        if (key === 'mind') {
          const dimensions = mind.value?.dimensions ?? []
          if (!dimensions.some((item) => item.primary_label === selectedMind.value)) {
            selectedMind.value = dimensions[0]?.primary_label ?? null
          }
        }
      } catch (error) {
        if (revision === dataRevision && requestRevisions[key] === moduleRequestRevision[key]) {
          moduleErrors.value[key] = apiErrorMessage(error)
        }
      } finally {
        if (revision === dataRevision && requestRevisions[key] === moduleRequestRevision[key]) {
          moduleLoading.value[key] = false
        }
      }
    }
    await Promise.all([
      settle('stream', fetchWorkbenchStream(streamParams)),
      settle('mind', fetchWorkbenchMind(mindParams)),
      settle('trend', fetchWorkbenchTrend(trendParams)),
    ])
    if (revision !== dataRevision) return
    if (seenIdentities.size > 1 || !dataIdentityConsistent(stream.value, mind.value, trend.value)) {
      globalError.value = 'Analysis Scheme 已切换，正在重新同步工作台口径。'
      if (!retried) {
        await refreshTaxonomy()
        await refreshData(true, true)
        return
      }
      stream.value = null
      mind.value = null
      trend.value = null
      moduleLoading.value = { stream: false, mind: false, trend: false }
      globalError.value = '工作台模块暂未取得同一 Analysis Scheme Version，请稍后重试。'
      return
    }
    await alignTaxonomyWithData()
  }

  /** 只重试指定模块；仅遇到 Scheme 身份切换时升级为三个模块重新对齐。 */
  async function refreshModule(
    key: WorkbenchModuleKey,
    suppressRetainedDataError = false,
  ): Promise<void> {
    const dataGeneration = dataRevision
    const requestRevision = ++moduleRequestRevision[key]
    moduleLoading.value[key] = true
    moduleErrors.value[key] = null
    try {
      let response: WorkbenchStreamResponse | WorkbenchMindResponse | WorkbenchTrendResponse
      if (key === 'stream') {
        response = await fetchWorkbenchStream(streamQueryParams(streamFilters.value))
      } else if (key === 'mind') {
        response = await fetchWorkbenchMind(aggregateQueryParams(mindFilters.value))
      } else {
        response = await fetchWorkbenchTrend(aggregateQueryParams(trendFilters.value))
      }
      if (dataGeneration !== dataRevision || requestRevision !== moduleRequestRevision[key]) return
      const identity = `${response.analysis_scheme_version_id}:${response.taxonomy_sha256}`
      const otherIdentities = [
        key === 'stream' ? null : stream.value,
        key === 'mind' ? null : mind.value,
        key === 'trend' ? null : trend.value,
      ]
        .filter((value): value is WorkbenchStreamResponse | WorkbenchMindResponse | WorkbenchTrendResponse => value !== null)
        .map((value) => `${value.analysis_scheme_version_id}:${value.taxonomy_sha256}`)
      if (otherIdentities.some((value) => value !== identity)) {
        globalError.value = 'Analysis Scheme 已切换，正在重新同步工作台口径。'
        await refreshData(true)
        return
      }
      if (key === 'stream') stream.value = response as WorkbenchStreamResponse
      else if (key === 'mind') {
        mind.value = response as WorkbenchMindResponse
        const dimensions = mind.value.dimensions
        if (!dimensions.some((item) => item.primary_label === selectedMind.value)) {
          selectedMind.value = dimensions[0]?.primary_label ?? null
        }
      } else trend.value = response as WorkbenchTrendResponse
      await alignTaxonomyWithData()
    } catch (error) {
      if (dataGeneration === dataRevision && requestRevision === moduleRequestRevision[key]) {
        const retainedData = key === 'stream'
          ? stream.value !== null
          : key === 'mind'
            ? mind.value !== null
            : trend.value !== null
        if (!suppressRetainedDataError || !retainedData) {
          moduleErrors.value[key] = apiErrorMessage(error)
        }
      }
    } finally {
      if (dataGeneration === dataRevision && requestRevision === moduleRequestRevision[key]) {
        moduleLoading.value[key] = false
      }
    }
  }

  /** 声音流完成一页滚动后读取下一游标页；末页回到第一页以纳入最新内容。 */
  async function advanceStream(): Promise<void> {
    if (moduleLoading.value.stream || !stream.value?.items.length) return
    const dataGeneration = dataRevision
    const requestRevision = ++moduleRequestRevision.stream
    moduleLoading.value.stream = true
    moduleErrors.value.stream = null
    try {
      const cursor = stream.value.has_more ? stream.value.next_cursor : undefined
      const fetchPage = (pageCursor?: string | null) => fetchWorkbenchStream({
        ...streamQueryParams(streamFilters.value),
        limit: 100,
        cursor: pageCursor || undefined,
      })
      let response: WorkbenchStreamResponse
      try {
        response = await fetchPage(cursor)
      } catch (error) {
        const cursorExpired = Boolean(cursor)
          && error instanceof AimaApiError
          && error.errors.some((item) => item.code === 'invalid_content_cursor')
        if (!cursorExpired) throw error
        // 用户长时间悬停、切换标签页后旧游标可能超过签名有效期；此时从当前
        // 筛选的第一页继续，而不是永久重试同一个失效游标。
        response = await fetchPage()
      }
      if (dataGeneration !== dataRevision || requestRevision !== moduleRequestRevision.stream) return
      const currentIdentity = `${response.analysis_scheme_version_id}:${response.taxonomy_sha256}`
      const otherIdentity = mind.value
        ? `${mind.value.analysis_scheme_version_id}:${mind.value.taxonomy_sha256}`
        : trend.value
          ? `${trend.value.analysis_scheme_version_id}:${trend.value.taxonomy_sha256}`
          : null
      if (otherIdentity && currentIdentity !== otherIdentity) {
        await refreshData(true)
        return
      }
      stream.value = response
    } catch {
      // 自动翻页失败时继续展示当前页，并在下一轮滚动后重试；不把瞬时网络波动
      // 变成遮挡声音流的持久错误。首次加载仍由 refreshData 暴露真实失败。
    } finally {
      if (dataGeneration === dataRevision && requestRevision === moduleRequestRevision.stream) {
        moduleLoading.value.stream = false
      }
    }
  }

  /** 周期补读只刷新两个聚合模块，避免每 1 小时把全量声音流遍历重置到第一页。 */
  async function refreshAggregates(): Promise<void> {
    await Promise.all([refreshModule('mind', true), refreshModule('trend', true)])
  }

  /** 聚合模块日期变更后短轮询到快照就绪/失败，避免只等 1 小时周期补读才出图。 */
  async function refreshAggregateModule(key: 'mind' | 'trend'): Promise<void> {
    await refreshModule(key)
    for (const pause of [700, 1400, 2800, 5600]) {
      const snapshot = key === 'mind' ? mind.value : trend.value
      if (!snapshot || (snapshot.snapshot_status !== 'preparing' && snapshot.snapshot_status !== 'refreshing')) return
      await new Promise((resolve) => setTimeout(resolve, pause))
      await refreshModule(key)
    }
  }

  /** 页面首次进入时并行准备参考数据和模块数据，首屏不等待非关键目录串行加载。 */
  async function initialize(): Promise<void> {
    await Promise.all([refreshReferenceData(), refreshData()])
  }

  /** 使一个模块进入“等待新筛选结果”状态，并让仍在途的旧请求不再覆盖新结果。 */
  function invalidateModule(key: WorkbenchModuleKey): void {
    moduleRequestRevision[key] += 1
    if (key === 'stream') stream.value = null
    else if (key === 'mind') {
      mind.value = null
      selectedMind.value = null
    } else trend.value = null
    moduleErrors.value[key] = null
    moduleLoading.value[key] = true
  }

  /** 恢复声音流近 30 个北京时间自然日和全维度未筛选状态。 */
  function resetStreamFilters(): void {
    streamFilters.value = defaultFilters()
  }

  /** 恢复品牌心智模块的近 30 天时间范围。 */
  function resetMindFilters(): void {
    mindFilters.value = defaultDateRange()
  }

  /** 恢复 UGC 趋势模块的近 30 天时间范围。 */
  function resetTrendFilters(): void {
    trendFilters.value = defaultDateRange()
  }

  /** 替换声音流筛选快照；页面用 debounce 合并连续勾选后再触发查询。 */
  function setStreamFilters(value: WorkbenchFilters): void {
    const nextFilters: WorkbenchFilters = {
      ...value,
      ...normalizeDateRange(value.dateFrom, value.dateTo),
      platforms: [...value.platforms],
      brandIds: [...value.brandIds],
      vehicleModelIds: [...value.vehicleModelIds],
      voiceTypes: [...value.voiceTypes],
      sentiments: [...value.sentiments],
      primaryLabels: [...value.primaryLabels],
      secondaryLabels: [...value.secondaryLabels],
    }
    streamFilters.value = taxonomy.value
      ? sanitizeTaxonomyFilters(nextFilters, taxonomy.value)
      : nextFilters
    invalidateModule('stream')
  }

  /** 替换品牌心智模块的时间范围。 */
  function setMindFilters(value: WorkbenchDateRange): void {
    mindFilters.value = normalizeDateRange(value.dateFrom, value.dateTo)
    invalidateModule('mind')
  }

  /** 替换 UGC 趋势模块的时间范围。 */
  function setTrendFilters(value: WorkbenchDateRange): void {
    trendFilters.value = normalizeDateRange(value.dateFrom, value.dateTo)
    invalidateModule('trend')
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
    const normalizedSpan = Math.max(5, Math.min(12, Math.round(columnSpan)))
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
      showNotice('工作台布局已保存。', 1_500)
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

  return {
    streamFilters,
    mindFilters,
    trendFilters,
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
    refreshModule,
    refreshAggregateModule,
    advanceStream,
    refreshAggregates,
    resetStreamFilters,
    resetMindFilters,
    resetTrendFilters,
    setStreamFilters,
    setMindFilters,
    setTrendFilters,
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
