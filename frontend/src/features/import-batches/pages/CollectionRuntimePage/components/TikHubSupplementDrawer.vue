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
  ImportBatchResponse,
  KeywordPackSummaryResponse,
} from '../../../../../generated/api/client'
import CollectionSearchConfigFields from '../../../../../shared/CollectionSearchConfigFields.vue'
import VehicleMultiSelect from '../../../../../shared/VehicleMultiSelect.vue'
import { isCollectionSearchConfigComplete } from '../../../../../shared/collectionSearchConfig'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { platformLabels, shortId } from '../../../format'

const props = defineProps<{
  modelValue: boolean
  capabilities: CollectionCapabilitiesResponse | null
  batches: ImportBatchResponse[]
  keywordPacks: KeywordPackSummaryResponse[]
  batchContentPlatforms: CollectionPlatform[]
  loadingBatchPlatforms: boolean
  creating: boolean
  initialBatchId?: string | null
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [request: CollectionRunCreateRequest]
  batchChange: [batchId: string]
}>()

const mode = ref<CollectionRunMode>('discovery')
const selectedPackIds = ref<string[]>([])
const selectedVehicleIds = ref<string[]>([])
const platforms = ref<CollectionPlatform[]>([])
const providerConfigId = ref('')
const importBatchId = ref('')
const includeComments = ref(true)
const includeSubComments = ref(false)
const searchConfigByPlatform = reactive<Partial<Record<CollectionPlatform, CollectionSearchConfig>>>({})
const validation = ref<string | null>(null)
const lastRequestedBatchId = ref('')
const supportedPlatforms: CollectionPlatform[] = [
  'xiaohongshu',
  'douyin',
  'weibo',
  'bilibili',
  'kuaishou',
]

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
      .filter((platform) => mode.value !== 'batch_supplement' || props.batchContentPlatforms.includes(platform))
      .filter((value, index, values) => values.indexOf(value) === index) ?? []
  )
})

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
    return (selectedPackIds.value.length > 0 || selectedVehicleIds.value.length > 0) && platforms.value.every((platform) => {
      const capability = searchCapability(platform)
      return capability && isCollectionSearchConfigComplete(capability, searchConfigByPlatform[platform])
    })
  }
  return !!importBatchId.value && !props.loadingBatchPlatforms
})

function requestBatchPlatforms(batchId: string): void {
  if (!batchId || lastRequestedBatchId.value === batchId) return
  lastRequestedBatchId.value = batchId
  emit('batchChange', batchId)
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    lastRequestedBatchId.value = props.initialBatchId ?? ''
    mode.value = props.initialBatchId ? 'batch_supplement' : 'discovery'
    importBatchId.value = props.initialBatchId ?? ''
    selectedPackIds.value = []
    selectedVehicleIds.value = []
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
  if (mode.value === 'batch_supplement') {
    requestBatchPlatforms(importBatchId.value)
  } else {
    lastRequestedBatchId.value = ''
  }
})

watch(importBatchId, (batchId, previous) => {
  platforms.value = []
  clearSearchConfigs()
  validation.value = null
  if (mode.value === 'batch_supplement' && batchId !== previous) {
    requestBatchPlatforms(batchId)
  }
})

watch(providerConfigId, () => {
  platforms.value = []
  clearSearchConfigs()
  validation.value = null
})

watch([includeComments, includeSubComments, availablePlatforms], () => {
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

function submit(): void {
  if (!providerConfigId.value) {
    validation.value = '请选择本次运行使用的采集渠道配置。'
    return
  }
  if (mode.value === 'batch_supplement' && props.loadingBatchPlatforms) {
    validation.value = '正在核对该批次可补采的平台，请稍后。'
    return
  }
  if (platforms.value.length === 0) {
    validation.value = '当前批次、采集渠道与采集内容组合没有可执行的平台。'
    return
  }
  if (mode.value === 'discovery' && selectedPackIds.value.length === 0 && selectedVehicleIds.value.length === 0) {
    validation.value = '请至少选择一个关键词包或车型。'
    return
  }
  if (mode.value === 'batch_supplement' && !importBatchId.value) {
    validation.value = '请选择要补采的数据导入批次。'
    return
  }
  validation.value = null
  emit('submit', {
    mode: mode.value,
    keyword_pack_ids: mode.value === 'discovery' ? selectedPackIds.value : [],
    vehicle_model_ids: mode.value === 'discovery' ? selectedVehicleIds.value : [],
    import_batch_id: mode.value === 'batch_supplement' ? importBatchId.value : null,
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
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="drawer-layer"
      @click.self="emit('update:modelValue', false)"
    >
      <aside
        class="drawer"
        role="dialog"
        aria-modal="true"
        aria-label="新建辅助补采"
      >
        <header>
          <div><strong>新建辅助补采</strong><span>创建辅助补采任务</span></div>
          <AimaButton
            variant="text"
            size="small"
            aria-label="关闭"
            @click="emit('update:modelValue', false)"
          >
            关闭
          </AimaButton>
        </header>

        <div class="drawer-body">
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
              :class="{ active: mode === 'batch_supplement' }"
              @click="mode = 'batch_supplement'"
            >
              基于已有批次补采
            </button>
          </nav>

          <AimaFeedbackBanner tone="info">
            {{ mode === 'discovery'
              ? '选择关键词包或车型；系统会冻结两类版本与解析后的车型别名，并按统一发现语义采集。'
              : '只允许选择已成功入库的批次；目标平台必须在该批次中真实存在，并满足当前采集渠道能力。' }}
          </AimaFeedbackBanner>

          <section
            v-if="mode === 'discovery'"
            class="form-card"
          >
            <label>关键词包（可多选）</label>
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
              当前没有可用的已启用词包。
            </p>
            <VehicleMultiSelect
              v-model="selectedVehicleIds"
              label="车型（可单独选择，也可与词包组合）"
            />
          </section>
          <section
            v-else
            class="form-card"
          >
            <label for="batch-select">数据导入批次</label>
            <select
              id="batch-select"
              v-model="importBatchId"
            >
              <option value="">
                请选择已成功入库批次
              </option>
              <option
                v-for="batch in batches"
                :key="batch.id"
                :value="batch.id"
              >
                {{ batch.source_filename || '未记录文件名' }} · {{ shortId(batch.id) }}
              </option>
            </select>
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

          <section class="form-card platform-card">
            <div class="section-title-row">
              <label>目标平台</label>
              <small>只显示当前采集渠道支持的平台</small>
            </div>
            <p
              v-if="mode === 'batch_supplement' && loadingBatchPlatforms"
              class="platform-state"
            >
              正在核对该批次的真实内容平台…
            </p>
            <div
              v-else
              class="platform-grid"
            >
              <button
                v-for="platform in availablePlatforms"
                :key="platform"
                type="button"
                :class="{ selected: platforms.includes(platform) }"
                :aria-pressed="platforms.includes(platform)"
                @click="togglePlatform(platform)"
              >
                <span class="check-box">{{ platforms.includes(platform) ? '✓' : '' }}</span>
                {{ platformLabels[platform] }}
              </button>
            </div>
            <p
              v-if="!loadingBatchPlatforms && availablePlatforms.length === 0"
              class="platform-state"
            >
              当前选择没有同时满足批次内容与采集渠道能力的平台。
            </p>
          </section>

          <section
            v-if="mode === 'discovery' && platforms.length"
            class="search-config-section"
          >
            <div
              v-for="platform in platforms"
              :key="platform"
              class="search-config-card"
            >
              <strong>逐平台发现参数 · {{ platformLabels[platform] }}</strong>
              <small>实际字段、选项和默认值由当前采集渠道能力决定</small>
              <CollectionSearchConfigFields
                v-if="searchCapability(platform) && searchConfigByPlatform[platform]"
                :model-value="searchConfigByPlatform[platform]!"
                :capability="searchCapability(platform)!"
                :platform-label="platformLabels[platform]"
                @update:model-value="searchConfigByPlatform[platform] = $event"
              />
            </div>
          </section>

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
            将发起真实外部采集请求，可能产生渠道费用；提交后由后台任务执行，可在采集运行中心查看进度。
          </AimaFeedbackBanner>
          <AimaFeedbackBanner
            v-if="validation"
            tone="error"
            role="alert"
          >
            {{ validation }}
          </AimaFeedbackBanner>
        </div>

        <footer>
          <AimaButton
            variant="secondary"
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
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer-layer { position: fixed; inset: 0; z-index: 110; background: rgb(17 22 37 / 94%); }
.drawer { position: absolute; inset: 0 0 0 auto; display: grid; width: min(510px, 100vw); height: 100vh; grid-template-rows: 76px minmax(0, 1fr) 72px; overflow: hidden; border-left: 1px solid var(--aima-border); background: var(--aima-surface); box-shadow: -10px 0 30px rgb(23 32 51 / 12%); }
header { display: flex; align-items: center; justify-content: space-between; padding: 0 24px; border-bottom: 1px solid var(--aima-border); }
header strong, header span { display: block; }
header strong { color: var(--aima-text); font-size: 18px; line-height: 24px; }
header span { margin-top: 4px; color: var(--aima-text-disabled); font-size: 12px; line-height: 18px; }
.drawer-body { display: flex; min-height: 0; flex-direction: column; gap: 20px; padding: 16px 24px; overflow-x: hidden; overflow-y: auto; }
.mode-tabs { display: flex; min-height: 40px; gap: 8px; }
.mode-tabs button { min-height: 40px; padding: 0 4px; border: 0; border-bottom: 2px solid transparent; color: var(--aima-text-muted); background: transparent; cursor: pointer; font-size: 13px; }
.mode-tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 500; }
.form-card { padding: 10px 11px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: var(--aima-surface); }
.form-card > label, .section-title-row > label { display: block; margin-bottom: 9px; color: var(--aima-text); font-size: 13px; font-weight: 500; line-height: 20px; }
select { width: 100%; height: 40px; padding: 0 12px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-control); color: var(--aima-text-secondary); background: var(--aima-surface); font-size: 13px; }
select:disabled { color: var(--aima-text-secondary); opacity: 1; }
.pack-choice-list { display: grid; gap: 4px; }
.pack-choice { display: grid; min-height: 32px; grid-template-columns: 16px minmax(0, 1fr) auto; align-items: center; gap: 8px; color: var(--aima-text-secondary); font-size: 13px; }
.pack-choice input, .content-option input { accent-color: var(--aima-primary); }
.pack-choice small { color: var(--aima-text-disabled); font-size: 11px; }
.section-title-row { display: flex; align-items: center; gap: 12px; }
.section-title-row > label { margin-bottom: 0; }
.section-title-row small { color: var(--aima-text-disabled); font-size: 11px; }
.platform-card { min-height: 150px; }
.platform-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; margin-top: 8px; }
.platform-grid button { display: flex; min-height: 32px; align-items: center; gap: 8px; padding: 0; border: 0; color: var(--aima-text-secondary); background: transparent; cursor: pointer; font-size: 13px; text-align: left; }
.check-box { display: inline-flex; width: 16px; height: 16px; flex: none; align-items: center; justify-content: center; border: 1px solid var(--aima-border-strong); border-radius: 4px; color: #fff; font-size: 11px; }
.platform-grid button.selected .check-box { border-color: var(--aima-primary); background: var(--aima-primary); }
.platform-state { margin: 8px 0 0; color: var(--aima-text-muted); font-size: 12px; line-height: 18px; }
.search-config-section { display: flex; flex-direction: column; gap: 12px; }
.search-config-card { padding: 10px 11px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: #f8fafc; }
.search-config-card > strong { display: block; color: var(--aima-text); font-size: 13px; font-weight: 500; }
.search-config-card > small { display: block; margin: 4px 0 10px; color: var(--aima-text-disabled); font-size: 11px; line-height: 18px; }
.content-options { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 16px; }
.content-option { display: grid; min-height: 32px; grid-template-columns: 16px 1fr auto; align-items: center; gap: 8px; color: var(--aima-text-secondary); font-size: 13px; }
.content-option small { color: var(--aima-text-disabled); font-size: 11px; }
.content-option.disabled { color: var(--aima-text-disabled); }
footer { display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding: 0 24px; border-top: 1px solid var(--aima-border); background: var(--aima-surface); }
footer :deep(.aima-button.is-primary) { min-width: 136px; }
footer :deep(.aima-button.is-secondary) { min-width: 88px; }
</style>
