import { computed, onScopeDispose, reactive, ref, watch, type Ref } from 'vue'
import type {
  CollectionCapabilitiesResponse, CollectionPlatform, CollectionSupplementPreviewResponse,
  CollectionSupplementTargetSelection,
} from '../../generated/api/client'
import { AimaApiError, apiErrorMessage } from '../../shared/api/http'
import { createSupplement, fetchSupplementCapabilities, previewSupplement } from './api'

/** 预览绑定当前选择与选项；请求序号同时防止日期往返和关闭重开竞态。 */
export function useCollectionSupplement(
  active: Ref<boolean>, targets: Ref<CollectionSupplementTargetSelection | null>,
  initialCapabilities?: () => CollectionCapabilitiesResponse | null,
) {
  const capabilities = ref<CollectionCapabilitiesResponse | null>(null)
  const preview = ref<CollectionSupplementPreviewResponse | null>(null)
  const platforms = ref<CollectionPlatform[]>([])
  const providerConfigId = ref('')
  const includeComments = ref(true)
  const includeSubComments = ref(false)
  const loading = ref(false)
  const creating = ref(false)
  const error = ref<string | null>(null)
  let epoch = 0
  let capabilityEpoch = 0
  const selected = computed(() => targets.value?.kind === 'selected')
  const provider = computed(() => capabilities.value?.provider_configs.find(
    (item) => item.id === providerConfigId.value,
  ))
  const requiredOperations = computed(() => [
    'content_detail', ...(includeComments.value ? ['comments'] : []),
    ...(includeSubComments.value ? ['sub_comments'] : []),
  ])
  /** 仅以服务端 Capability 判断当前渠道是否支持全部采集层级。 */
  function supports(platform: CollectionPlatform): boolean {
    return Boolean(provider.value && capabilities.value?.capabilities.some((item) =>
      item.provider === provider.value?.provider && item.platform === platform
      && requiredOperations.value.every((operation) => item.operations.some((value) => value === operation)),
    ))
  }
  const request = computed(() => targets.value ? {
    targets: targets.value,
    platforms: selected.value ? [] : platforms.value,
    include_comments: includeComments.value,
    include_sub_comments: includeSubComments.value,
  } : null)
  const signature = computed(() => JSON.stringify({ active: active.value, request: request.value }))
  const canSubmit = computed(() => active.value && !loading.value && !creating.value
    && preview.value !== null && preview.value.target_count > 0 && platforms.value.length > 0
    && platforms.value.every(supports))

  /** 每次范围或选项变化立即清空旧预览，过期响应不能恢复提交资格。 */
  async function refreshPreview(): Promise<void> {
    const version = ++epoch
    const current = request.value
    preview.value = null
    error.value = null
    loading.value = false
    if (!active.value || !current) return
    loading.value = true
    try {
      const result = await previewSupplement(current)
      if (version !== epoch) return
      if (!selected.value) {
        const retained = platforms.value.filter((platform) => result.platforms.some((item) => item.platform === platform))
        if (retained.length !== platforms.value.length) {
          platforms.value = retained
          return
        }
      }
      preview.value = result
      if (selected.value) platforms.value = result.platforms.map((item) => item.platform)
    } catch (reason) {
      if (version === epoch) error.value = apiErrorMessage(reason)
    } finally {
      if (version === epoch) loading.value = false
    }
  }
  watch(active, async (open) => {
    const version = ++capabilityEpoch
    ++epoch
    preview.value = null
    platforms.value = []
    providerConfigId.value = ''
    includeComments.value = true
    includeSubComments.value = false
    error.value = null
    if (!open) return
    try {
      const result = initialCapabilities?.() ?? await fetchSupplementCapabilities()
      if (version !== capabilityEpoch) return
      capabilities.value = result
      if (result.provider_configs.length === 1) providerConfigId.value = result.provider_configs[0]?.id ?? ''
    } catch (reason) {
      if (version === capabilityEpoch) error.value = apiErrorMessage(reason)
    }
  }, { immediate: true, flush: 'sync' })
  watch(targets, (current, previous) => {
    if (!current || current.kind !== previous?.kind) platforms.value = []
  }, { flush: 'sync' })
  watch(includeComments, (enabled) => { if (!enabled) includeSubComments.value = false })
  watch(signature, () => { void refreshPreview() }, { immediate: true, flush: 'sync' })
  onScopeDispose(() => { ++epoch; ++capabilityEpoch })

  /** 日期允许用户缩小平台范围，明确勾选入口必须保留全部平台。 */
  function togglePlatform(platform: CollectionPlatform): void {
    if (selected.value || (!platforms.value.includes(platform) && !supports(platform))) return
    platforms.value = platforms.value.includes(platform)
      ? platforms.value.filter((item) => item !== platform) : [...platforms.value, platform]
  }
  /** 共享组件通过动作修改渠道，不直接改写传入的状态。 */
  function setProvider(value: string): void { providerConfigId.value = value }
  /** 已选内容的评论固定开启，日期入口保留选项。 */
  function setComments(value: boolean): void { if (!selected.value) includeComments.value = value }
  /** 回复只能在一级评论开启时采集。 */
  function setSubComments(value: boolean): void { includeSubComments.value = value && includeComments.value }
  /** 409 只更新预览，必须由用户再次确认，禁止自动创建变化后的目标。 */
  async function create() {
    const current = targets.value
    const confirmed = preview.value
    if (!canSubmit.value || !current || !confirmed) return null
    creating.value = true
    error.value = null
    try {
      return await createSupplement({
        mode: 'content_supplement', supplement_targets: current,
        expected_target_count: confirmed.target_count,
        expected_target_fingerprint: confirmed.target_fingerprint,
        platforms: platforms.value.map((platform) => ({ platform, provider_config_id: providerConfigId.value })),
        include_comments: includeComments.value, include_sub_comments: includeSubComments.value,
      })
    } catch (reason) {
      if (reason instanceof AimaApiError && reason.errors.some((item) => item.code === 'collection_supplement_targets_changed')) {
        await refreshPreview()
        error.value = '目标范围已变化，已更新数量，请重新确认后创建。'
      } else error.value = apiErrorMessage(reason)
      return null
    } finally { creating.value = false }
  }
  return reactive({
    capabilities, preview, platforms, providerConfigId, includeComments, includeSubComments,
    loading, creating, error, selected, canSubmit, supports, togglePlatform, refreshPreview, create,
    setProvider, setComments, setSubComments,
  })
}
export type CollectionSupplementFormState = ReturnType<typeof useCollectionSupplement>
