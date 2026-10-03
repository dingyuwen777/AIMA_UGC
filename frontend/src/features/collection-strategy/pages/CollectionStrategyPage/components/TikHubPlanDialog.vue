<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import type {
  CollectionCapabilitiesResponse,
  CollectionPlanCreateRequest,
  CollectionPlanResponse,
  CollectionPlanUpdateRequest,
  CollectionPlatform,
  CollectionSearchCapabilityResponse,
  CollectionSearchConfig,
  KeywordPackResponse,
  KeywordPackSummaryResponse,
} from '../../../../../generated/api/client'
import CollectionSearchConfigFields from '../../../../../shared/CollectionSearchConfigFields.vue'
import BrandMultiSelect from '../../../../../shared/BrandMultiSelect.vue'
import {
  fixedCollectionSearchConfig,
  isCollectionSearchConfigComplete,
} from '../../../../../shared/collectionSearchConfig'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaModalContainer from '../../../../../shared/ui/AimaModalContainer.vue'
import TikHubCommentPolicySummary from './TikHubCommentPolicySummary.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import { planExecutionReason } from '../../../eligibility'
import { COLLECTION_PLATFORM_OPTIONS, COLLECTION_SCHEDULE_PRESETS } from '../../../presentation'

const props = defineProps<{
  packs: KeywordPackSummaryResponse[]
  packDetails: Record<string, KeywordPackResponse>
  capabilities: CollectionCapabilitiesResponse | null
  saving: boolean
  error?: string | null
  loadingPackDetails: boolean
  initialPlan?: CollectionPlanResponse | null
}>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{
  submitCreate: [request: CollectionPlanCreateRequest]
  submitUpdate: [request: CollectionPlanUpdateRequest]
  loadPackDetails: [packIds: string[]]
}>()

const platformOptions = COLLECTION_PLATFORM_OPTIONS
const planType = ref<'tikhub' | 'wisersone'>('wisersone')
const name = ref('')
const scheduleExpr = ref('0 */6 * * *')
const enabled = ref(true)
const commentPolicy = ref<'adaptive' | 'full'>('adaptive')
const selectedPacks = ref<string[]>([])
const brandScope = ref<'all_active' | 'selected'>('all_active')
const selectedBrands = ref<string[]>([])
const providerByPlatform = reactive<Partial<Record<CollectionPlatform, string>>>({})
const searchConfigByPlatform = reactive<Partial<Record<CollectionPlatform, CollectionSearchConfig>>>({})
const editing = computed(() => props.initialPlan !== null && props.initialPlan !== undefined)

const selectedPlatforms = computed(() =>
  platformOptions
    .filter((item) => providerByPlatform[item.value])
    .map((item) => ({
      platform: item.value,
      provider_config_id: providerByPlatform[item.value]!,
      search_config: searchConfigByPlatform[item.value] ?? {},
    })),
)

const eligibilityReason = computed(() => {
  if (brandScope.value === 'selected' && selectedBrands.value.length === 0) {
    return '请至少选择一个品牌，或改为全部启用品牌。'
  }
  if (planType.value === 'wisersone') return null

  const pendingProvider = platformOptions.find(
    (item) => isPlatformSelected(item.value) && !providerByPlatform[item.value],
  )
  if (pendingProvider) return `请选择${pendingProvider.label}的采集服务配置。`

  const incompletePlatform = platformOptions.find((item) => {
    if (!providerByPlatform[item.value]) return false
    const capability = searchCapability(item.value)
    return !capability || !isCollectionSearchConfigComplete(capability, searchConfigByPlatform[item.value])
  })
  if (incompletePlatform) return `请完整选择${incompletePlatform.label}的采集参数。`

  return planExecutionReason({
    keywordPackIds: selectedPacks.value,
    platforms: selectedPlatforms.value,
    packDetails: props.packDetails,
    capabilities: props.capabilities,
  })
})

const brandScopeSummary = computed(() =>
  brandScope.value === 'all_active'
    ? '全部启用品牌及车型'
    : `已指定 ${selectedBrands.value.length} 个品牌`,
)

watch(open, (value) => {
  if (!value) return
  const plan = props.initialPlan
  planType.value = plan?.plan_type ?? 'wisersone'
  name.value = plan?.name ?? ''
  scheduleExpr.value = plan?.schedule_expr ?? '0 0 * * *'
  enabled.value = plan?.enabled ?? true
  commentPolicy.value = plan?.comment_policy ?? 'adaptive'
  selectedPacks.value = [...(plan?.keyword_pack_ids ?? [])]
  selectedBrands.value = [...(plan?.brand_ids ?? [])]
  brandScope.value = selectedBrands.value.length ? 'selected' : 'all_active'
  for (const option of platformOptions) {
    delete providerByPlatform[option.value]
    delete searchConfigByPlatform[option.value]
  }
  for (const platform of plan?.platforms ?? []) {
    providerByPlatform[platform.platform] = platform.provider_config_id
    searchConfigByPlatform[platform.platform] = { ...platform.search_config }
  }
  if (selectedPacks.value.length) emit('loadPackDetails', [...selectedPacks.value])
}, { immediate: true })

watch(selectedPacks, (packIds) => {
  if (packIds.length) emit('loadPackDetails', [...packIds])
}, { deep: true })

/** 返回当前平台真实支持关键词搜索的 Provider 配置。 */
function configsFor(platform: CollectionPlatform) {
  const providers = new Set(
    (props.capabilities?.capabilities ?? [])
      .filter((item) => item.provider === 'tikhub' && item.platform === platform && item.operations.includes('keyword_search'))
      .map((item) => item.provider),
  )
  return (props.capabilities?.provider_configs ?? []).filter((item) => providers.has(item.provider))
}

/** 解析已选 Provider 对应的动态 Search Capability。 */
function searchCapability(platform: CollectionPlatform): CollectionSearchCapabilityResponse | null {
  const providerConfig = props.capabilities?.provider_configs.find(
    (item) => item.id === providerByPlatform[platform],
  )
  if (!providerConfig) return null
  return props.capabilities?.capabilities.find(
    (item) => item.provider === providerConfig.provider && item.platform === platform,
  )?.search ?? null
}

/** Provider 变化时按后端 Capability 重建固定 Search Config 默认值。 */
function resetSearchConfig(platform: CollectionPlatform): void {
  const capability = searchCapability(platform)
  searchConfigByPlatform[platform] = capability ? fixedCollectionSearchConfig(capability) : {}
}

/** 用属性是否存在区分“尚未选择”和“已选择但等待选择 Provider”。 */
function isPlatformSelected(platform: CollectionPlatform): boolean {
  return Object.prototype.hasOwnProperty.call(providerByPlatform, platform)
}

/** 添加或移除平台；唯一 Provider 自动选中，多 Provider 保留人工选择。 */
function togglePlatform(platform: CollectionPlatform): void {
  if (isPlatformSelected(platform)) {
    delete providerByPlatform[platform]
    delete searchConfigByPlatform[platform]
    return
  }
  const configs = configsFor(platform)
  if (configs.length === 0) return
  providerByPlatform[platform] = configs.length === 1 ? configs[0]!.id : ''
  if (providerByPlatform[platform]) resetSearchConfig(platform)
}

/** 资格完整时提交创建或下一版本更新；历史运行的冻结配置不会被重写。 */
function submit(): void {
  if (props.saving || (planType.value === 'tikhub' && props.loadingPackDetails) || !name.value.trim() || eligibilityReason.value) return
  const common = {
    plan_type: planType.value,
    comment_policy: planType.value === 'tikhub' ? commentPolicy.value : null,
    name: name.value.trim(),
    schedule_expr: scheduleExpr.value,
    keyword_pack_ids: planType.value === 'tikhub' ? selectedPacks.value : [],
    brand_ids: brandScope.value === 'selected' ? [...selectedBrands.value] : [],
    platforms: planType.value === 'tikhub' ? selectedPlatforms.value : [],
    enabled: enabled.value,
  }
  if (props.initialPlan) {
    emit('submitUpdate', {
      ...common,
      expected_version: props.initialPlan.schedule_version,
    })
    return
  }
  emit('submitCreate', common)
}
</script>

<template>
  <AimaModalContainer
    v-model="open"
    :label="editing ? '编辑采集计划' : '新建采集计划'"
    width="960px"
    height="820px"
    :close-disabled="saving"
  >
    <template #header>
      <header>
        <div>
          <h2>{{ editing ? '编辑采集计划' : '新建采集计划' }}</h2>
          <p>{{ planType === 'wisersone' ? '按执行频率下载网站过去 24 小时的 Excel，自动按品牌过滤并导入系统' : '通过 TikHub 按关键词持续发现并采集内容' }}</p>
        </div>
        <AimaButton
          variant="text"
          aria-label="关闭"
          :disabled="saving"
          @click="open = false"
        >
          <AimaIcon name="close" />
        </AimaButton>
      </header>
    </template>
    <div class="body">
      <AimaFeedbackBanner
        v-if="error"
        tone="error"
        role="alert"
      >
        {{ error }}
      </AimaFeedbackBanner>
      <fieldset
        class="form-content"
        :disabled="saving"
      >
        <fieldset>
          <legend>采集计划类型</legend>
          <label class="check"><input
            v-model="planType"
            type="radio"
            value="wisersone"
            :disabled="editing"
          >WisersOne 网站下载</label>
          <label class="check"><input
            v-model="planType"
            type="radio"
            value="tikhub"
            :disabled="editing"
          >TikHub 采集</label>
          <small v-if="editing">已有计划的类型保持固定；需要另一类型时新建计划。</small>
        </fieldset>
        <div class="two-column">
          <label><strong>计划名称</strong><input
            v-model="name"
            maxlength="200"
            placeholder="例如：爱玛新品口碑追踪"
          ></label>
          <label><strong>执行频率</strong><span class="schedule-field">
            <select
              v-model="scheduleExpr"
              aria-label="执行频率"
            >
              <option
                v-if="!COLLECTION_SCHEDULE_PRESETS.some((preset) => preset.value === scheduleExpr)"
                :value="scheduleExpr"
              >{{ scheduleExpr }}</option>
              <option
                v-for="preset in COLLECTION_SCHEDULE_PRESETS"
                :key="preset.value"
                :value="preset.value"
              >{{ preset.label }}</option>
            </select><em>北京时间</em>
          </span><small>重新启用后从下一周期执行，不补跑停用期间任务。</small></label>
        </div>
        <div class="two-column">
          <fieldset v-if="planType === 'tikhub'">
            <legend>搜索条件 · 关键词包</legend>
            <label
              v-for="pack in packs"
              :key="pack.id"
              class="check"
            >
              <input
                v-model="selectedPacks"
                type="checkbox"
                :value="pack.id"
              >{{ pack.name }} · v{{ pack.version }}{{ pack.enabled ? '' : ' · 已停用' }}
            </label>
            <p v-if="packs.length === 0">
              请先创建可用的关键词包；关键词发现必须从词包取得搜索词。
            </p>
          </fieldset>
          <fieldset>
            <legend>内容过滤 · 品牌</legend>
            <label class="check"><input
              v-model="brandScope"
              type="radio"
              value="all_active"
            >全部启用品牌及车型</label>
            <label class="check"><input
              v-model="brandScope"
              type="radio"
              value="selected"
            >指定品牌</label>
            <BrandMultiSelect
              v-if="brandScope === 'selected'"
              v-model="selectedBrands"
              label="指定品牌（可多选）"
            />
            <small>{{ brandScopeSummary }}；每次运行保存当时的过滤范围。</small>
          </fieldset>
        </div>
        <fieldset v-if="planType === 'tikhub'">
          <legend>目标平台</legend>
          <div class="platforms">
            <div
              v-for="option in platformOptions"
              :key="option.value"
              :class="['platform', { active: isPlatformSelected(option.value), unavailable: configsFor(option.value).length === 0 }]"
            >
              <label class="platform-toggle">
                <input
                  type="checkbox"
                  :checked="isPlatformSelected(option.value)"
                  :disabled="configsFor(option.value).length === 0"
                  @change="togglePlatform(option.value)"
                >
                <strong>{{ option.label }}</strong>
                <small>{{ configsFor(option.value).length ? isPlatformSelected(option.value) ? '已启用' : '未选择' : '暂无可用配置' }}</small>
              </label>
              <select
                v-if="isPlatformSelected(option.value) && configsFor(option.value).length > 1"
                v-model="providerByPlatform[option.value]"
                :aria-label="`${option.label}采集服务`"
                @change="resetSearchConfig(option.value)"
              >
                <option
                  value=""
                  disabled
                >
                  请选择采集服务
                </option>
                <option
                  v-for="config in configsFor(option.value)"
                  :key="config.id"
                  :value="config.id"
                >
                  {{ config.display_name }}
                </option>
              </select>
              <div
                v-if="providerByPlatform[option.value] && searchCapability(option.value)"
                class="platform-search"
              >
                <CollectionSearchConfigFields
                  :model-value="searchConfigByPlatform[option.value] ?? {}"
                  :capability="searchCapability(option.value)!"
                  :platform-label="option.label"
                  @update:model-value="searchConfigByPlatform[option.value] = $event"
                />
              </div>
            </div>
          </div>
        </fieldset>
        <fieldset v-if="planType === 'tikhub'">
          <legend>评论采集策略</legend>
          <div class="policy-options">
            <label :class="['policy-option', { selected: commentPolicy === 'adaptive' }]">
              <span class="policy-option-title"><input
                v-model="commentPolicy"
                type="radio"
                value="adaptive"
              >自适应采集（推荐）</span>
              <TikHubCommentPolicySummary policy="adaptive" />
            </label>
            <label :class="['policy-option', { selected: commentPolicy === 'full' }]">
              <span class="policy-option-title"><input
                v-model="commentPolicy"
                type="radio"
                value="full"
              >全量采集</span>
              <TikHubCommentPolicySummary policy="full" />
            </label>
          </div>
        </fieldset>
        <label class="switch"><strong>{{ editing ? '保存后启用计划' : '创建后启用计划' }}</strong><input
          v-model="enabled"
          type="checkbox"
          :aria-label="editing ? '保存后启用计划' : '创建后启用计划'"
        ></label>
      </fieldset>
      <div
        v-if="eligibilityReason && (planType === 'wisersone' || (selectedPacks.length && platformOptions.some((item) => isPlatformSelected(item.value))))"
        class="eligibility"
        role="status"
      >
        {{ loadingPackDetails ? '正在读取实时资格…' : eligibilityReason }}
      </div>
      <AimaFeedbackBanner
        v-if="planType === 'tikhub'"
        :tone="commentPolicy === 'full' ? 'warning' : 'info'"
      >
        {{ commentPolicy === 'full' ? '全量采集可能显著增加 TikHub 请求与费用。' : '实际运行可能产生 TikHub 请求费用。' }}当前没有请求预算或金额上限。
      </AimaFeedbackBanner>
      <AimaFeedbackBanner
        v-else
        tone="info"
      >
        每次新运行固定下载过去 24 小时；网站生成 Excel 较慢时持续等待，不设置 30 分钟总上限。下载完成后自动预检和导入，不自动触发智能分析。修改计划只影响后续运行。
      </AimaFeedbackBanner>
    </div>
    <template #footer>
      <footer>
        <AimaButton
          :disabled="saving"
          @click="open = false"
        >
          取消
        </AimaButton>
        <AimaButton
          variant="primary"
          :disabled="saving || (planType === 'tikhub' && loadingPackDetails) || !name.trim() || !!eligibilityReason"
          :title="eligibilityReason || undefined"
          @click="submit"
        >
          {{ saving ? '保存中…' : editing ? '保存修改' : '保存计划' }}
        </AimaButton>
      </footer>
    </template>
  </AimaModalContainer>
</template>

<style scoped>
header { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 20px 24px; border-bottom: 1px solid var(--aima-border); }
h2 { margin: 0; font-size: 20px; line-height: 28px; }
header p { margin: 5px 0 0; color: var(--aima-text-secondary); font-size: 13px; line-height: 20px; }
.body { padding: 24px; }
.form-content { min-width: 0; margin: 0; padding: 0; border: 0; }
.two-column,.platforms,.policy-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
label,fieldset { min-width: 0; margin: 0 0 22px; }
fieldset { padding: 0; border: 0; }
label strong,legend { display: block; margin-bottom: 8px; color: var(--aima-text); font-size: 14px; font-weight: 600; }
input:not([type='checkbox']):not([type='radio']),select { width: 100%; height: 40px; padding: 0 11px; border: 1px solid var(--aima-border); border-radius: 8px; background: var(--aima-color-bg-white); }
input[type='checkbox'],input[type='radio'] { width: 16px; height: 16px; flex: none; accent-color: var(--aima-primary); }
.check { display: inline-flex; align-items: center; gap: 8px; margin: 0 16px 8px 0; font-size: 13px; }
:deep(.brand-select) { margin: 8px 0 0; padding: 0; border: 0; border-radius: 0; }
:deep(.brand-select legend) { margin-bottom: 8px; padding: 0; font-size: 13px; }
:deep(.brand-select__options label) { min-height: 32px; height: 32px; padding: 0; border: 0; border-radius: 0; font-size: 12px; }
:deep(.brand-select__options label:has(input:checked)) { border: 0; color: var(--aima-text-secondary); background: transparent; }
:deep(.brand-select__options input) { width: 16px; height: 16px; }
small,fieldset p { color: var(--aima-text-secondary); font-size: 12px; line-height: 20px; }
label > small { display: block; margin-top: 5px; }
.platform { padding: 14px; border: 1px solid var(--aima-border); border-radius: 8px; }
.platform.active,.policy-option.selected { border-color: var(--aima-primary); background: #fff5f8; }
.platform.unavailable { opacity: .6; }
.platform-toggle { display: flex; align-items: center; gap: 8px; margin: 0; cursor: pointer; }
.platform-toggle strong { margin: 0; }
.platform-toggle small { margin-left: auto; }
.platform-search,.platform > select { margin-top: 12px; }
.schedule-field { display: flex; align-items: center; border: 1px solid var(--aima-border); border-radius: 8px; }
.schedule-field select { border: 0; }
.schedule-field em { padding: 0 10px; color: var(--aima-text-secondary); font-size: 12px; font-style: normal; white-space: nowrap; }
.policy-option { margin: 0; padding: 16px; border: 1px solid var(--aima-border); border-radius: 8px; cursor: pointer; }
.policy-option-title { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-size: 14px; font-weight: 600; }
.switch { display: flex; align-items: center; justify-content: space-between; }
.switch strong { margin: 0; }
.eligibility { margin-bottom: 16px; padding: 10px; border: 1px solid #ffc7cc; border-radius: 8px; color: #b4232d; background: #fff5f6; font-size: 13px; }
footer { display: flex; justify-content: flex-end; gap: 12px; padding: 18px 24px; border-top: 1px solid var(--aima-border); }
:global(.aima-modal-container[aria-label$='采集计划'] > .aima-modal-body) { --aima-scrollbar-size: 5px; }
:global(.aima-modal-container[aria-label$='采集计划']) { max-width: calc(100% - 48px); }
@media (max-width: 720px) { .two-column,.platforms,.policy-options { grid-template-columns: minmax(0, 1fr); } .body { padding: 18px; } header,footer { padding: 16px 18px; } }
</style>
