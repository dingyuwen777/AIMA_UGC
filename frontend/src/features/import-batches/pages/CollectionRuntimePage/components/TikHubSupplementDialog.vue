<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import type {
  CollectionCapabilitiesResponse,
  CollectionCapabilityResponseOperationsItem,
  CollectionPlatform,
  CollectionRunCreateRequest,
  CollectionRunMode,
  CollectionSearchCapabilityResponse,
  CollectionSearchConfig,
  CollectionSupplementPlatformDiagnosticResponse,
  CollectionBatchSupplementTargetResponse,
  GetCollectionDateSupplementEligibilityParams,
  KeywordPackSummaryResponse,
} from '../../../../../generated/api/client'
import CollectionSearchConfigFields from '../../../../../shared/CollectionSearchConfigFields.vue'
import BrandMultiSelect from '../../../../../shared/BrandMultiSelect.vue'
import { isCollectionSearchConfigComplete } from '../../../../../shared/collectionSearchConfig'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaModalContainer from '../../../../../shared/ui/AimaModalContainer.vue'
import AimaDateRange from '../../../../../shared/ui/AimaDateRange.vue'
import { beijingDayBoundary } from '../../../../../shared/domain/beijingTime'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { platformLabels } from '../../../format'

const props = defineProps<{
  modelValue: boolean
  capabilities: CollectionCapabilitiesResponse | null
  keywordPacks: KeywordPackSummaryResponse[]
  supplementContentPlatforms: CollectionPlatform[]
  supplementDiagnostics: CollectionSupplementPlatformDiagnosticResponse[]
  loadingSupplementPlatforms: boolean
  creating: boolean
  supplementTargets: CollectionBatchSupplementTargetResponse[]
  eligibilityReady: boolean
  eligibilityError: string | null
  error: string | null
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [request: CollectionRunCreateRequest]
  dateChange: [range: GetCollectionDateSupplementEligibilityParams | null]
}>()

const mode = ref<CollectionRunMode>('discovery')
const selectedPackIds = ref<string[]>([])
const brandScope = ref<'all_active' | 'selected'>('all_active')
const selectedBrandIds = ref<string[]>([])
const platforms = ref<CollectionPlatform[]>([])
const providerConfigId = ref('')
const publishedFrom = ref('')
const publishedTo = ref('')
const includeComments = ref(true)
const includeSubComments = ref(false)
const searchConfigByPlatform = reactive<Partial<Record<CollectionPlatform, CollectionSearchConfig>>>({})
const validation = ref<string | null>(null)
const supportedPlatforms: CollectionPlatform[] = [
  'xiaohongshu',
  'douyin',
  'weibo',
  'bilibili',
  'kuaishou',
]

const dateSelection = computed<GetCollectionDateSupplementEligibilityParams | null>(() => {
  const from = beijingDayBoundary(publishedFrom.value, 'start')
  const to = beijingDayBoundary(publishedTo.value, 'end')
  return from && to && from <= to ? { published_from: from, published_to: to } : null
})

/** 日期组件一次提交完整范围，避免中间半选日期触发资格查询。 */
function updateDateRange(range: { from: string; to: string }): void {
  publishedFrom.value = range.from
  publishedTo.value = range.to
  validation.value = null
  emit('dateChange', dateSelection.value)
}

const selectedScopeCount = computed(() => props.supplementDiagnostics
  .filter((item) => platforms.value.includes(item.platform))
  .reduce((total, item) => total + item.direct_target_count + item.resolution_candidate_count + item.blocked_count, 0))
const eligibleTargetCount = computed(() => props.supplementTargets
  .filter((item) => platforms.value.includes(item.platform))
  .reduce((total, item) => total + item.target_count, 0))

function isCollectionPlatform(value: string): value is CollectionPlatform {
  return supportedPlatforms.includes(value as CollectionPlatform)
}

const selectedProvider = computed(() =>
  props.capabilities?.provider_configs.find((item) => item.id === providerConfigId.value) ?? null,
)

const requiredOperations = computed<CollectionCapabilityResponseOperationsItem[]>(() => {
  const operations: CollectionCapabilityResponseOperationsItem[] = ['content_detail']
  if (mode.value === 'discovery') operations.push('keyword_search')
  if (includeComments.value) operations.push('comments')
  if (includeSubComments.value) operations.push('sub_comments')
  return operations
})

const availablePlatforms = computed(() => {
  const provider = selectedProvider.value
  if (!provider) return []
  return (
    props.capabilities?.capabilities
      .filter((item) => item.provider === provider.provider)
      .filter((item) => requiredOperations.value.every((operation) => item.operations.includes(operation)))
      .map((item) => item.platform)
      .filter(isCollectionPlatform)
      .filter((platform) => mode.value !== 'date_supplement' || props.supplementContentPlatforms.includes(platform))
      .filter((value, index, values) => values.indexOf(value) === index) ?? []
  )
})

const unavailablePlatforms = computed(() =>
  mode.value === 'date_supplement'
    ? props.supplementDiagnostics.filter((item) => !availablePlatforms.value.includes(item.platform))
    : [],
)

/** 从 Eligibility 读取平台数量，避免页面自行推断 Provider 身份。 */
function platformDiagnostic(platform: CollectionPlatform): CollectionSupplementPlatformDiagnosticResponse | undefined {
  return props.supplementDiagnostics.find((item) => item.platform === platform)
}

/** 把稳定阻塞分类转换为用户可执行的来源修复说明。 */
function unavailableReason(item: CollectionSupplementPlatformDiagnosticResponse): string {
  if (!selectedProvider.value) return '先选择采集渠道'
  if (item.direct_target_count > 0) return '当前渠道不支持所选采集内容'
  if (item.resolution_candidate_count > 0) return `有 ${item.resolution_candidate_count} 条受支持的分享链接，创建任务后将解析原生 ID`
  if (item.block_reasons.exact_resolution_unavailable) return `有 ${item.block_reasons.exact_resolution_unavailable} 条分享链接无法确认对应内容；请在原始内容补充平台原生 ID`
  if (item.platform === 'weibo') return `有 ${item.blocked_count} 条内容不可补采；微博长文章不支持评论补采，其他内容请补充平台原生 ID`
  return `有 ${item.blocked_count} 条内容缺少可验证的原生 ID；请在原始内容补充原始内容链接`
}

function searchCapability(platform: CollectionPlatform): CollectionSearchCapabilityResponse | null {
  const provider = selectedProvider.value
  if (!provider) return null
  return props.capabilities?.capabilities.find(
    (item) => item.provider === provider.provider && item.platform === platform,
  )?.search ?? null
}

function clearSearchConfigs(): void {
  for (const platform of supportedPlatforms) delete searchConfigByPlatform[platform]
}

const canSubmit = computed(() => {
  if (props.creating || !providerConfigId.value || platforms.value.length === 0) return false
  if (mode.value === 'discovery') {
    return (
      (brandScope.value === 'all_active' || selectedBrandIds.value.length > 0) &&
      selectedPackIds.value.length > 0 && platforms.value.every((platform) => {
        const capability = searchCapability(platform)
        return capability && isCollectionSearchConfigComplete(capability, searchConfigByPlatform[platform])
      })
    )
  }
  return dateSelection.value !== null && props.eligibilityReady && !props.eligibilityError && !props.loadingSupplementPlatforms
})

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    publishedFrom.value = ''
    publishedTo.value = ''
    mode.value = 'date_supplement'
    selectedPackIds.value = []
    brandScope.value = 'all_active'
    selectedBrandIds.value = []
    platforms.value = []
    includeComments.value = true
    includeSubComments.value = false
    clearSearchConfigs()
    validation.value = null
    providerConfigId.value =
      props.capabilities?.provider_configs.length === 1
        ? (props.capabilities.provider_configs[0]?.id ?? '')
        : ''
  },
)

watch(mode, () => {
  platforms.value = []
  clearSearchConfigs()
  validation.value = null
  emit('dateChange', mode.value === 'date_supplement' ? dateSelection.value : null)
})

watch(providerConfigId, () => {
  platforms.value = []
  clearSearchConfigs()
  validation.value = null
})

watch([includeComments, includeSubComments, availablePlatforms, () => props.loadingSupplementPlatforms], () => {
  if (mode.value === 'date_supplement' && props.loadingSupplementPlatforms) return
  platforms.value = platforms.value.filter((platform) => availablePlatforms.value.includes(platform))
  for (const platform of supportedPlatforms) {
    if (!platforms.value.includes(platform)) delete searchConfigByPlatform[platform]
  }
  validation.value = null
})

watch(includeComments, (enabled) => {
  if (!enabled) includeSubComments.value = false
})

function togglePack(packId: string): void {
  selectedPackIds.value = selectedPackIds.value.includes(packId)
    ? selectedPackIds.value.filter((value) => value !== packId)
    : [...selectedPackIds.value, packId]
}

function togglePlatform(platform: CollectionPlatform): void {
  if (platforms.value.includes(platform)) {
    platforms.value = platforms.value.filter((value) => value !== platform)
    delete searchConfigByPlatform[platform]
    return
  }
  platforms.value = [...platforms.value, platform]
  const capability = searchCapability(platform)
  if (mode.value === 'discovery' && capability) {
    searchConfigByPlatform[platform] = { ...capability.manual_default }
  }
}

/** 提交前只校验当前真实 Capability/来源/词包选择，不从 Figma 示例推导平台能力。 */
function submit(): void {
  if (!providerConfigId.value) {
    validation.value = '请选择本次运行使用的采集渠道配置。'
    return
  }
  if (mode.value === 'date_supplement' && props.loadingSupplementPlatforms) {
    validation.value = '正在核对该日期范围可补采的平台，请稍后。'
    return
  }
  if (platforms.value.length === 0) {
    validation.value = '当前日期范围、采集渠道与采集内容组合没有可执行的平台。'
    return
  }
  if (mode.value === 'discovery' && selectedPackIds.value.length === 0) {
    validation.value = '请至少选择一个关键词包作为搜索条件。'
    return
  }
  if (mode.value === 'discovery' && brandScope.value === 'selected' && selectedBrandIds.value.length === 0) {
    validation.value = '请至少选择一个品牌，或改为全部启用品牌。'
    return
  }
  if (mode.value === 'date_supplement' && (!dateSelection.value || !props.eligibilityReady || props.eligibilityError)) {
    validation.value = props.eligibilityError || '请选择发布时间范围，并等待资格查询完成。'
    return
  }
  validation.value = null
  emit('submit', {
    mode: mode.value,
    keyword_pack_ids: mode.value === 'discovery' ? selectedPackIds.value : [],
    brand_ids: mode.value === 'discovery' && brandScope.value === 'selected' ? selectedBrandIds.value : [],
    ...(mode.value === 'date_supplement' ? dateSelection.value : {}),
    platforms: platforms.value.map((platform) => ({
      platform,
      provider_config_id: providerConfigId.value,
      ...(mode.value === 'discovery'
        ? { search_config: searchConfigByPlatform[platform] }
        : {}),
    })),
    include_comments: includeComments.value,
    include_sub_comments: includeSubComments.value,
  })
}
</script>

<template>
  <AimaModalContainer
    :model-value="modelValue"
    label="新建辅助补采"
    width="840px"
    height="800px"
    :close-disabled="creating"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <header class="dialog-header">
        <div><strong>新建辅助补采</strong><span>创建辅助补采任务</span></div>
        <AimaButton
          variant="text"
          size="small"
          aria-label="关闭"
          :disabled="creating"
          @click="emit('update:modelValue', false)"
        >
          关闭
        </AimaButton>
      </header>
    </template>

    <div class="dialog-body">
      <AimaFeedbackBanner
        v-if="error"
        tone="error"
        role="alert"
      >
        {{ error }}
      </AimaFeedbackBanner>
      <nav class="mode-tabs">
        <button
          type="button"
          :class="{ active: mode === 'discovery' }"
          @click="mode = 'discovery'"
        >
          独立发现新内容
        </button>
        <button
          type="button"
          :class="{ active: mode === 'date_supplement' }"
          @click="mode = 'date_supplement'"
        >
          按发布时间补采
        </button>
      </nav>

      <AimaFeedbackBanner tone="info">
        {{ mode === 'discovery'
          ? '关键词包提供 Provider 搜索词；内容入库前按冻结的品牌与车型目录过滤。'
          : '按北京时间选择已入库内容的发布时间范围，任务创建时固定内容清单，再补充详情和评论。' }}
      </AimaFeedbackBanner>

      <section
        v-if="mode === 'discovery'"
        class="form-card"
      >
        <label>搜索条件 · 关键词包（至少选择一项）</label>
        <div class="pack-choice-list">
          <label
            v-for="pack in keywordPacks"
            :key="pack.id"
            class="pack-choice"
          >
            <input
              type="checkbox"
              :checked="selectedPackIds.includes(pack.id)"
              @change="togglePack(pack.id)"
            >
            <span>{{ pack.name }}</span>
            <small>{{ pack.keyword_count }} 词 · v{{ pack.version }}</small>
          </label>
        </div>
        <p
          v-if="keywordPacks.length === 0"
          class="platform-state"
        >
          当前没有可用的已启用词包。请先在“采集策略”创建并启用至少一个词包。
        </p>
      </section>
      <section
        v-else
        class="form-card"
      >
        <label>内容发布时间 · 北京时间</label>
        <AimaDateRange
          :from="publishedFrom"
          :to="publishedTo"
          label="内容发布时间"
          @update:range="updateDateRange"
        />
        <small>包含开始日和结束日的全天；范围内没有发布时间的内容不会入选。</small>
      </section>

      <section
        v-if="mode === 'discovery'"
        class="form-card brand-card"
      >
        <fieldset>
          <legend>内容过滤条件 · 品牌</legend>
          <label><input
            v-model="brandScope"
            type="radio"
            value="all_active"
          >全部启用品牌及车型</label>
          <label><input
            v-model="brandScope"
            type="radio"
            value="selected"
          >指定品牌</label>
        </fieldset>
        <BrandMultiSelect
          v-if="brandScope === 'selected'"
          v-model="selectedBrandIds"
          label="指定品牌（可多选）"
        />
        <small
          v-if="brandScope === 'selected' && selectedBrandIds.length === 0"
          class="validation-inline"
          role="status"
        >请至少选择一个品牌，或改为全部启用品牌。</small>
        <small>品牌与车型目录随本次任务冻结；指定品牌可多选。</small>
      </section>

      <section
        v-if="(capabilities?.provider_configs.length ?? 0) > 0"
        class="form-card"
      >
        <label for="provider-select">采集渠道</label>
        <select
          id="provider-select"
          v-model="providerConfigId"
          :disabled="capabilities?.provider_configs.length === 1"
        >
          <option value="">
            请选择采集渠道
          </option>
          <option
            v-for="config in capabilities?.provider_configs"
            :key="config.id"
            :value="config.id"
          >
            {{ config.display_name }}
          </option>
        </select>
      </section>
      <AimaFeedbackBanner
        v-else
        tone="error"
        role="alert"
      >
        当前没有可用采集渠道，无法创建辅助补采任务。
      </AimaFeedbackBanner>

      <section class="form-card platform-card">
        <div class="section-title-row">
          <label>目标平台与采集渠道</label>
          <small>只显示当前采集渠道真实支持的平台</small>
        </div>
        <p
          v-if="mode === 'date_supplement' && loadingSupplementPlatforms"
          class="platform-state"
        >
          正在核对该日期范围的真实内容平台…
        </p>
        <div
          v-else
          class="platform-grid"
        >
          <div
            v-for="platform in availablePlatforms"
            :key="platform"
            class="platform-option"
            :class="{ selected: platforms.includes(platform) }"
          >
            <button
              type="button"
              :aria-pressed="platforms.includes(platform)"
              @click="togglePlatform(platform)"
            >
              <span><strong>{{ platformLabels[platform] }}</strong><small v-if="!platforms.includes(platform)">点击选择</small></span>
              <span v-if="platforms.includes(platform)">{{ selectedProvider?.display_name }}</span>
            </button>
            <small v-if="mode === 'date_supplement' && platformDiagnostic(platform)">
              可直接补采 {{ platformDiagnostic(platform)?.direct_target_count }} 条；
              待解析 {{ platformDiagnostic(platform)?.resolution_candidate_count }} 条；
              不可补采 {{ platformDiagnostic(platform)?.blocked_count }} 条
            </small>
            <CollectionSearchConfigFields
              v-if="mode === 'discovery' && platforms.includes(platform) && searchCapability(platform) && searchConfigByPlatform[platform]"
              class="platform-search-fields"
              :model-value="searchConfigByPlatform[platform]!"
              :capability="searchCapability(platform)!"
              :platform-label="platformLabels[platform]"
              @update:model-value="searchConfigByPlatform[platform] = $event"
            />
          </div>
          <div
            v-for="item in unavailablePlatforms"
            :key="`unavailable-${item.platform}`"
            class="platform-option unavailable"
            aria-disabled="true"
          >
            <strong>{{ platformLabels[item.platform] }}</strong>
            <small>{{ unavailableReason(item) }}</small>
          </div>
        </div>
        <p
          v-if="!loadingSupplementPlatforms && availablePlatforms.length === 0"
          class="platform-state"
        >
          当前选择没有可直接补采的平台；请查看各平台的身份与渠道说明。
        </p>
      </section>

      <AimaFeedbackBanner
        v-if="mode === 'date_supplement' && eligibilityError"
        tone="error"
        role="alert"
      >
        {{ eligibilityError }}
        <AimaButton
          variant="text"
          size="small"
          @click="emit('dateChange', dateSelection)"
        >
          重试资格查询
        </AimaButton>
      </AimaFeedbackBanner>
      <p
        v-if="mode === 'date_supplement' && eligibilityReady"
        class="platform-state"
        role="status"
      >
        已选 {{ platforms.length }} 个平台 · 可补采 {{ eligibleTargetCount }} 条 · 预计处理 {{ selectedScopeCount }} 条内容（含身份缺口）
      </p>

      <section class="form-card content-card">
        <label>采集内容</label>
        <div class="content-options">
          <label class="content-option disabled">
            <input
              type="checkbox"
              checked
              disabled
            >
            <span>内容详情</span><small>固定执行</small>
          </label>
          <label class="content-option">
            <input
              v-model="includeComments"
              type="checkbox"
            >
            <span>评论</span><small>可选</small>
          </label>
          <label
            class="content-option"
            :class="{ disabled: !includeComments }"
          >
            <input
              v-model="includeSubComments"
              type="checkbox"
              :disabled="!includeComments"
            >
            <span>二级回复</span><small>依赖评论</small>
          </label>
        </div>
      </section>

      <AimaFeedbackBanner tone="warning">
        将发起真实外部采集请求，可能产生渠道费用；提交后自动执行，可在采集运行中心查看进度。
      </AimaFeedbackBanner>
      <AimaFeedbackBanner
        v-if="validation"
        tone="error"
        role="alert"
      >
        {{ validation }}
      </AimaFeedbackBanner>
    </div>

    <template #footer>
      <footer class="dialog-footer">
        <AimaButton
          variant="secondary"
          :disabled="creating"
          size="small"
          @click="emit('update:modelValue', false)"
        >
          取消
        </AimaButton>
        <AimaButton
          variant="primary"
          :disabled="!canSubmit"
          @click="submit"
        >
          {{ creating ? '创建中…' : '创建补采任务' }}
        </AimaButton>
      </footer>
    </template>
  </AimaModalContainer>
</template>

<style scoped>
.dialog-header { display: flex; height: 76px; align-items: center; justify-content: space-between; padding: 0 24px; border-bottom: 1px solid var(--aima-border); background: var(--aima-surface); }
.dialog-header strong, .dialog-header span { display: block; }
.dialog-header strong { color: var(--aima-text); font-size: 18px; font-weight: 700; line-height: 24px; }
.dialog-header span { margin-top: 4px; color: var(--aima-color-text-tertiary); font-size: 12px; line-height: 18px; }
.dialog-body { display: flex; min-height: 0; flex-direction: column; gap: 20px; padding: 16px 24px 12px; }
.mode-tabs { display: flex; min-height: 40px; gap: 8px; }
.mode-tabs button { min-height: 40px; padding: 0 4px; border: 0; border-bottom: 2px solid transparent; color: var(--aima-text-muted); background: transparent; cursor: pointer; font-size: 13px; line-height: 20px; }
.mode-tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 500; }
.form-card { padding: 10px 11px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.form-card > label, .section-title-row > label { display: block; margin-bottom: 9px; color: var(--aima-text); font-size: 13px; font-weight: 500; line-height: 20px; }
select { width: 100%; height: 32px; padding: 0 12px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-lg); color: var(--aima-text-secondary); background: var(--aima-surface); font-size: 13px; }
select:disabled { color: var(--aima-text-secondary); opacity: 1; }
.pack-choice-list { display: grid; gap: 4px; }
.pack-choice { display: grid; min-height: 32px; grid-template-columns: 16px minmax(0, 1fr) auto; align-items: center; gap: 8px; color: var(--aima-text-secondary); font-size: 13px; }
.pack-choice input, .content-option input { accent-color: var(--aima-primary); }
.pack-choice small { color: var(--aima-text-disabled); font-size: 11px; }
.section-title-row { display: flex; align-items: center; gap: 12px; }
.section-title-row > label { margin-bottom: 0; }
.section-title-row small { color: var(--aima-text-disabled); font-size: 11px; }
.platform-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.platform-option { padding: 10px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.platform-option.selected { border-color: var(--aima-primary); background: var(--aima-color-primary-light); }
.platform-option.unavailable { background: var(--aima-surface-muted); }
.platform-option button { display: flex; width: 100%; min-height: 38px; align-items: center; justify-content: space-between; gap: 12px; padding: 0; border: 0; color: var(--aima-text-secondary); background: transparent; cursor: pointer; font-size: 12px; text-align: left; }
.platform-option strong, .platform-option small { display: block; }
.platform-option strong { color: var(--aima-text); font-size: 14px; font-weight: 500; line-height: 22px; }
.platform-option small { margin-top: 5px; color: var(--aima-text-disabled); font-size: 11px; }
.platform-option button > span + span { color: var(--aima-text-muted); font-size: 11px; }
.platform-search-fields { margin-top: 12px; }
.brand-card { min-height: 114px; }
.brand-card fieldset { display: flex; flex-wrap: wrap; gap: 8px 16px; margin: 0 0 12px; padding: 0; border: 0; }
.brand-card legend { width: 100%; margin-bottom: 2px; color: var(--aima-text); font-size: 13px; font-weight: 500; }
.brand-card fieldset label { display: inline-flex; align-items: center; gap: 5px; color: var(--aima-text-secondary); font-size: 12px; }
.brand-card > small { display: block; margin-top: 8px; color: var(--aima-text-muted); font-size: 11px; }
.platform-state { margin: 8px 0 0; color: var(--aima-text-muted); font-size: 12px; line-height: 18px; }
.content-options { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 16px; }
.content-option { display: grid; min-height: 32px; grid-template-columns: 16px 1fr auto; align-items: center; gap: 8px; color: var(--aima-text-secondary); font-size: 13px; }
.content-option small { color: var(--aima-text-disabled); font-size: 11px; }
.content-option.disabled { color: var(--aima-text-disabled); }
.dialog-footer { display: flex; height: 72px; align-items: center; justify-content: flex-end; gap: 10px; padding: 0 24px; border-top: 1px solid var(--aima-border); background: var(--aima-surface); }
.dialog-footer :deep(.aima-button.is-primary) { min-width: 136px; }
.dialog-footer :deep(.aima-button.is-secondary) { min-width: 88px; }
@media (max-width: 600px) { .platform-grid, .content-options { grid-template-columns: 1fr; } .section-title-row { flex-wrap: wrap; } }
</style>
