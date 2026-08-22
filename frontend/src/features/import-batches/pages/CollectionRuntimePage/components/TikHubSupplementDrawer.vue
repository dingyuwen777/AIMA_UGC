<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type {
  CollectionCapabilitiesResponse,
  CollectionCapabilityResponseOperationsItem,
  CollectionPlatform,
  CollectionRunCreateRequest,
  CollectionRunMode,
  ImportBatchResponse,
} from '../../../../../generated/api/client'
import { platformLabels, shortId } from '../../../format'

const props = defineProps<{
  modelValue: boolean
  capabilities: CollectionCapabilitiesResponse | null
  batches: ImportBatchResponse[]
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
const keywordInput = ref('')
const keywords = ref<string[]>([])
const platforms = ref<CollectionPlatform[]>([])
const providerConfigId = ref('')
const importBatchId = ref('')
const includeComments = ref(true)
const includeSubComments = ref(false)
const validation = ref<string | null>(null)
const lastRequestedBatchId = ref('')
const supportedPlatforms: CollectionPlatform[] = [
  'xhs',
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

const canSubmit = computed(() => {
  if (props.creating || !providerConfigId.value || platforms.value.length === 0) return false
  if (mode.value === 'discovery') return keywords.value.length > 0 || keywordInput.value.trim().length > 0
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
    keywordInput.value = ''
    keywords.value = []
    platforms.value = []
    includeComments.value = true
    includeSubComments.value = false
    validation.value = null
    providerConfigId.value =
      props.capabilities?.provider_configs.length === 1
        ? (props.capabilities.provider_configs[0]?.id ?? '')
        : ''
  },
)

watch(mode, () => {
  platforms.value = []
  validation.value = null
  if (mode.value === 'batch_supplement') {
    requestBatchPlatforms(importBatchId.value)
  } else {
    lastRequestedBatchId.value = ''
  }
})

watch(importBatchId, (batchId, previous) => {
  platforms.value = []
  validation.value = null
  if (mode.value === 'batch_supplement' && batchId !== previous) {
    requestBatchPlatforms(batchId)
  }
})

watch([providerConfigId, includeComments, includeSubComments, availablePlatforms], () => {
  platforms.value = platforms.value.filter((platform) => availablePlatforms.value.includes(platform))
  validation.value = null
})

watch(includeComments, (enabled) => {
  if (!enabled) includeSubComments.value = false
})

function addKeywords(): void {
  const values = keywordInput.value
    .split(/[,，\n]/u)
    .map((value) => value.trim())
    .filter(Boolean)
  for (const value of values) {
    if (!keywords.value.some((existing) => existing.toLocaleLowerCase() === value.toLocaleLowerCase())) {
      keywords.value.push(value)
    }
  }
  keywords.value = keywords.value.slice(0, 100)
  keywordInput.value = ''
}

function togglePlatform(platform: CollectionPlatform): void {
  platforms.value = platforms.value.includes(platform)
    ? platforms.value.filter((value) => value !== platform)
    : [...platforms.value, platform]
}

function submit(): void {
  addKeywords()
  if (!providerConfigId.value) {
    validation.value = '请选择本次运行使用的 TikHub Provider 配置。'
    return
  }
  if (mode.value === 'batch_supplement' && props.loadingBatchPlatforms) {
    validation.value = '正在核对该 Batch 可补采的平台，请稍后。'
    return
  }
  if (platforms.value.length === 0) {
    validation.value = '当前 Batch、Provider 与采集内容组合没有可执行的平台。'
    return
  }
  if (mode.value === 'discovery' && keywords.value.length === 0) {
    validation.value = '请输入至少一个一次性 Discovery 关键词。'
    return
  }
  if (mode.value === 'batch_supplement' && !importBatchId.value) {
    validation.value = '请选择要补采的 Excel Import Batch。'
    return
  }
  validation.value = null
  emit('submit', {
    mode: mode.value,
    keywords: mode.value === 'discovery' ? keywords.value : [],
    import_batch_id: mode.value === 'batch_supplement' ? importBatchId.value : null,
    platforms: platforms.value.map((platform) => ({
      platform,
      provider_config_id: providerConfigId.value,
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
        aria-label="新建 TikHub 辅助补采"
      >
        <header>
          <div><strong>新建 TikHub 辅助补采</strong><span>创建正式 Collection Run / Job</span></div><button
            type="button"
            aria-label="关闭"
            @click="emit('update:modelValue', false)"
          >
            ×
          </button>
        </header>
        <nav class="mode-tabs">
          <button
            type="button"
            :class="{ active: mode === 'discovery' }"
            @click="mode = 'discovery'"
          >
            独立发现新内容
          </button><button
            type="button"
            :class="{ active: mode === 'batch_supplement' }"
            @click="mode = 'batch_supplement'"
          >
            基于已有批次补采
          </button>
        </nav>

        <p class="mode-note">
          {{ mode === 'discovery' ? '输入一次性 Discovery 关键词，主动从平台发现帖子；关键词仅冻结到本次 Run。' : '只允许选择已成功入库的 Excel Batch；平台必须在该 Batch 中真实存在，并满足当前 Provider 能力。' }}
        </p>

        <section v-if="mode === 'discovery'">
          <label>一次性搜索关键词</label>
          <div class="keyword-box">
            <span
              v-for="keyword in keywords"
              :key="keyword"
            >{{ keyword }} <button
              type="button"
              :aria-label="`删除关键词 ${keyword}`"
              @click="keywords = keywords.filter((value) => value !== keyword)"
            >×</button></span><input
              v-model="keywordInput"
              placeholder="输入关键词后回车"
              @keydown.enter.prevent="addKeywords"
              @blur="addKeywords"
            >
          </div>
        </section>
        <section v-else>
          <label for="batch-select">Excel Import Batch</label>
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

        <section v-if="(capabilities?.provider_configs.length ?? 0) > 1">
          <label for="provider-select">TikHub Provider 配置</label>
          <select
            id="provider-select"
            v-model="providerConfigId"
          >
            <option value="">
              请选择配置
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

        <section>
          <label>目标平台</label>
          <p
            v-if="mode === 'batch_supplement' && loadingBatchPlatforms"
            class="platform-state"
          >
            正在核对该 Batch 的真实 Content 平台…
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
              @click="togglePlatform(platform)"
            >
              {{ platformLabels[platform] }} <b v-if="platforms.includes(platform)">✓</b>
            </button>
          </div>
          <p
            v-if="!loadingBatchPlatforms && availablePlatforms.length === 0"
            class="platform-state"
          >
            当前选择没有同时满足 Batch Content 与 Provider Capability 的平台。
          </p>
        </section>

        <section>
          <label>采集内容</label>
          <div class="content-options">
            <label class="option selected"><input
              type="checkbox"
              checked
              disabled
            ><span>▣</span><strong>内容详情</strong><small>固定执行</small></label>
            <label
              class="option"
              :class="{ selected: includeComments }"
            ><input
              v-model="includeComments"
              type="checkbox"
            ><span>◌</span><strong>评论</strong><small>可选</small></label>
            <label
              class="option"
              :class="{ selected: includeSubComments, disabled: !includeComments }"
            ><input
              v-model="includeSubComments"
              type="checkbox"
              :disabled="!includeComments"
            ><span>≡</span><strong>二级回复</strong><small>依赖评论</small></label>
          </div>
        </section>

        <section class="flow">
          <label>执行方式</label>
          <div>Collection Run → Durable Job → Worker → TikHub → Raw → Mapper → 全局 Relevance → ContentIngestionService → PostgreSQL</div>
        </section>
        <p class="cost-note">
          ⚠ 将发起真实 TikHub 请求，可能产生费用；提交后由 Worker 后台执行。
        </p>
        <p
          v-if="validation"
          class="validation"
          role="alert"
        >
          {{ validation }}
        </p>
        <footer>
          <button
            type="button"
            @click="emit('update:modelValue', false)"
          >
            取消
          </button><button
            class="primary"
            type="button"
            :disabled="!canSubmit"
            @click="submit"
          >
            {{ creating ? '创建中…' : '创建补采任务' }}
          </button>
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer-layer { position: fixed; inset: 0; z-index: 110; background: rgb(22 29 43 / 40%); }
.drawer { position: absolute; inset: 0 0 0 auto; width: 480px; overflow-y: auto; padding: 0 24px 90px; background: #fff; box-shadow: -10px 0 30px rgb(23 32 51 / 12%); }
header { display: flex; min-height: 72px; align-items: center; justify-content: space-between; }
header strong, header span { display: block; }
header strong { font-size: 18px; }
header span { margin-top: 6px; color: #768094; font-size: 12px; }
header > button { border: 0; color: #475166; background: transparent; cursor: pointer; font-size: 25px; }
.mode-tabs { display: grid; grid-template-columns: 1fr 1fr; overflow: hidden; border: 1px solid #d9dee8; border-radius: 6px; }
.mode-tabs button { height: 42px; border: 0; color: #3c4557; background: #fff; cursor: pointer; }
.mode-tabs button.active { color: #fff; background: var(--aima-primary); font-weight: 600; }
.mode-note { min-height: 48px; color: #6f798c; font-size: 12px; line-height: 1.8; }
section { margin-top: 24px; }
section > label, .flow > label { display: block; margin-bottom: 10px; color: #283245; font-size: 13px; font-weight: 600; }
select, .keyword-box { width: 100%; min-height: 42px; border: 1px solid #d9dee8; border-radius: 7px; background: #fff; }
select { padding: 0 11px; color: #3c4557; }
.keyword-box { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; padding: 7px 9px; }
.keyword-box > span { padding: 5px 8px; border-radius: 5px; color: #485266; background: #f1f3f6; font-size: 11px; }
.keyword-box span button { border: 0; color: #778093; background: transparent; cursor: pointer; }
.keyword-box input { min-width: 135px; flex: 1; border: 0; outline: 0; }
.platform-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
.platform-grid button { height: 42px; border: 1px solid #d9dee8; border-radius: 7px; color: #3c4557; background: #fff; cursor: pointer; font-size: 12px; }
.platform-grid button.selected { border-color: #ff8bb4; color: var(--aima-primary); background: #fff5f8; }
.platform-state { margin: 8px 0; color: #7b8494; font-size: 12px; }
.content-options { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.option { position: relative; display: grid; min-height: 86px; grid-template-columns: 26px 1fr; align-content: center; padding: 10px; border: 1px solid #d9dee8; border-radius: 7px; cursor: pointer; }
.option input { position: absolute; top: 8px; right: 8px; accent-color: var(--aima-primary); }
.option span { grid-row: 1 / 3; color: #566174; font-size: 20px; }
.option strong { align-self: end; font-size: 12px; }
.option small { color: #8790a1; font-size: 10px; }
.option.selected { border-color: #ff8bb4; color: var(--aima-primary); background: #fff8fa; }
.option.disabled { cursor: default; opacity: .55; }
.flow div { padding: 14px; border: 1px solid #dfe4ec; border-radius: 7px; color: #596477; background: #fafbfc; font-size: 11px; line-height: 1.8; }
.cost-note { padding: 12px; border: 1px solid #ffd0a8; border-radius: 7px; color: #b54708; background: #fff8f0; font-size: 11px; line-height: 1.6; }
.validation { padding: 11px; border: 1px solid #ffc7cc; border-radius: 7px; color: #b4232d; background: #fff5f6; font-size: 11px; }
footer { position: absolute; right: 0; bottom: 0; left: 0; display: grid; grid-template-columns: 1fr 1.8fr; gap: 12px; padding: 15px 24px; border-top: 1px solid var(--aima-border); background: #fff; }
footer button { height: 44px; border: 1px solid #d8dde6; border-radius: 7px; background: #fff; cursor: pointer; }
footer .primary { border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); }
footer button:disabled { opacity: .65; cursor: default; }
</style>
