<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import type { ResourceLifecycleResponse } from '../../../generated/api/client'
import { apiErrorMessage } from '../../../shared/api/http'
import { formatDateTime } from '../../../shared/domain/beijingTime'
import AimaButton from '../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../shared/ui/AimaFeedbackBanner.vue'
import {
  addProviderConfig,
  archiveProvider,
  deleteArchivedProvider,
  editProviderConfig,
  fetchArchivedProviders,
  fetchProviderConfigs,
  fetchProviderDeleteEligibility,
  restoreArchivedProvider,
  testProviderConnection,
  type ProviderConfigCreateRequest,
  type ProviderConfigResponse,
  type ProviderConfigUpdateRequest,
  type ProviderConnectionTestResponse,
} from '../api'

const props = defineProps<{
  providerKind: 'llm' | 'collection'
}>()

const items = ref<ProviderConfigResponse[]>([])
const archivedItems = ref<ResourceLifecycleResponse[]>([])
const selectedId = ref('')
const loading = ref(false)
const archivedLoading = ref(false)
const saving = ref(false)
const testing = ref(false)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)
const connectionResult = ref<ProviderConnectionTestResponse | null>(null)

const draft = reactive({
  id: '',
  provider: '',
  displayName: '',
  baseUrl: '',
  model: '',
  apiKey: '',
  timeoutSeconds: 45,
  maxRetries: 3,
  maxConcurrency: 5,
  maxRps: '',
  enabled: true,
  isDefault: false,
})

const isLlm = computed(() => props.providerKind === 'llm')
const panelTitle = computed(() => (isLlm.value ? 'AI 模型服务' : 'TikHub 采集服务'))
const panelDescription = computed(() => (
  isLlm.value
    ? '管理 AI 模型的服务地址、模型和访问密钥。保存后，新建的 AI 分析任务会使用最新配置。'
    : '管理 TikHub 的服务地址、访问密钥和请求限制。保存后，新建的采集任务会使用最新配置。'
))
const selectedItem = computed(() => items.value.find((item) => item.id === selectedId.value) ?? null)
const formValid = computed(() => {
  if (!draft.displayName.trim() || !draft.provider.trim() || !draft.baseUrl.trim()) return false
  if (isLlm.value && !draft.model.trim()) return false
  if (!draft.id && !draft.apiKey.trim()) return false
  return draft.timeoutSeconds > 0
    && draft.maxRetries >= 0
    && draft.maxRetries <= 20
    && draft.maxConcurrency > 0
    && draft.maxConcurrency <= 5000
    && (!draft.maxRps || (Number(draft.maxRps) > 0 && Number(draft.maxRps) <= 10000))
})

onMounted(load)

async function load(preferredId?: string): Promise<void> {
  loading.value = true
  error.value = null
  try {
    items.value = (await fetchProviderConfigs(props.providerKind)).items
    const selected = items.value.find((item) => item.id === (preferredId ?? selectedId.value))
      ?? items.value.find((item) => item.is_default)
      ?? items.value[0]
    if (selected) selectItem(selected, true)
    else resetDraft(true)
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    loading.value = false
  }
}

async function loadArchived(): Promise<void> {
  archivedLoading.value = true
  error.value = null
  try {
    archivedItems.value = (await fetchArchivedProviders()).items
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    archivedLoading.value = false
  }
}

function onArchivedToggle(event: Event): void {
  if ((event.currentTarget as HTMLDetailsElement).open) void loadArchived()
}

function resetDraft(preserveFeedback = false): void {
  selectedId.value = ''
  Object.assign(draft, {
    id: '',
    provider: isLlm.value ? 'openai_compatible' : 'tikhub',
    displayName: isLlm.value ? '默认 AI 模型' : 'TikHub',
    baseUrl: '',
    model: '',
    apiKey: '',
    timeoutSeconds: 45,
    maxRetries: 3,
    maxConcurrency: 5,
    maxRps: '',
    enabled: true,
    isDefault: isLlm.value,
  })
  connectionResult.value = null
  error.value = null
  if (!preserveFeedback) notice.value = null
}

function selectItem(item: ProviderConfigResponse, preserveFeedback = false): void {
  selectedId.value = item.id
  Object.assign(draft, {
    id: item.id,
    provider: item.provider,
    displayName: item.display_name,
    baseUrl: item.base_url,
    model: item.model ?? '',
    apiKey: '',
    timeoutSeconds: item.timeout_seconds,
    maxRetries: item.max_retries,
    maxConcurrency: item.max_concurrency,
    maxRps: item.max_rps == null ? '' : String(item.max_rps),
    enabled: item.enabled,
    isDefault: item.is_default,
  })
  connectionResult.value = null
  error.value = null
  if (!preserveFeedback) notice.value = null
}

function maxRpsValue(): number | null {
  const value = draft.maxRps.trim()
  return value ? Number(value) : null
}

async function save(): Promise<void> {
  if (!formValid.value) return
  saving.value = true
  error.value = null
  notice.value = null
  try {
    let saved: ProviderConfigResponse
    let success: string
    if (draft.id) {
      const body: ProviderConfigUpdateRequest = {
        display_name: draft.displayName.trim(),
        base_url: draft.baseUrl.trim(),
        model: isLlm.value ? draft.model.trim() : null,
        timeout_seconds: draft.timeoutSeconds,
        max_retries: draft.maxRetries,
        max_concurrency: draft.maxConcurrency,
        max_rps: maxRpsValue(),
        enabled: draft.enabled,
        is_default: isLlm.value ? draft.isDefault : false,
        ...(draft.apiKey.trim() ? { api_key: draft.apiKey } : {}),
      }
      saved = await editProviderConfig(draft.id, body)
      success = draft.apiKey.trim()
        ? '配置已保存，访问密钥已更新；新任务将使用新配置。'
        : '配置已保存；新任务将使用新配置，正在运行的任务不受影响。'
    } else {
      const body: ProviderConfigCreateRequest = {
        provider_kind: props.providerKind,
        provider: draft.provider.trim(),
        display_name: draft.displayName.trim(),
        base_url: draft.baseUrl.trim(),
        model: isLlm.value ? draft.model.trim() : null,
        api_key: draft.apiKey,
        timeout_seconds: draft.timeoutSeconds,
        max_retries: draft.maxRetries,
        max_concurrency: draft.maxConcurrency,
        max_rps: maxRpsValue(),
        enabled: draft.enabled,
        is_default: isLlm.value ? draft.isDefault : false,
      }
      saved = await addProviderConfig(body)
      success = '配置已创建；新任务无需重启服务即可使用。'
    }
    draft.apiKey = ''
    await load(saved.id)
    notice.value = success
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

async function testConnection(): Promise<void> {
  if (!draft.id) return
  testing.value = true
  error.value = null
  notice.value = null
  connectionResult.value = null
  try {
    connectionResult.value = await testProviderConnection(draft.id)
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    testing.value = false
  }
}

async function archiveCurrent(): Promise<void> {
  const item = selectedItem.value
  if (!item) return
  if (!window.confirm(`确认归档服务配置“${item.display_name}”吗？归档后新任务不会再使用它，历史任务的冻结配置不会改变。`)) return
  saving.value = true
  error.value = null
  notice.value = null
  try {
    await archiveProvider(item.id)
    await Promise.all([load(), loadArchived()])
    notice.value = '服务配置已归档。'
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

async function restoreArchived(item: ResourceLifecycleResponse): Promise<void> {
  saving.value = true
  error.value = null
  notice.value = null
  try {
    await restoreArchivedProvider(item.id)
    await Promise.all([load(item.id), loadArchived()])
    notice.value = '服务配置已恢复，当前保持停用且不会自动成为默认配置。'
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

async function permanentlyDelete(item: ResourceLifecycleResponse): Promise<void> {
  saving.value = true
  error.value = null
  notice.value = null
  try {
    const eligibility = await fetchProviderDeleteEligibility(item.id)
    if (!eligibility.eligible) {
      error.value = (eligibility.blocking_reasons ?? []).join('；') || '该服务配置已有业务历史，只能保留归档记录。'
      return
    }
    if (!window.confirm(`确认永久删除已归档服务配置“${item.name}”吗？此操作只允许从未进入业务历史的配置。`)) return
    await deleteArchivedProvider(item.id)
    await loadArchived()
    notice.value = '未进入业务历史的服务配置已永久删除。'
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="provider-layout">
    <section class="card provider-list">
      <header>
        <div>
          <h2>{{ panelTitle }}</h2>
          <p>{{ panelDescription }}</p>
        </div>
        <AimaButton size="small" @click="resetDraft()">新增配置</AimaButton>
      </header>

      <AimaFeedbackBanner v-if="error" tone="error" role="alert">{{ error }}</AimaFeedbackBanner>
      <AimaFeedbackBanner v-if="notice" tone="success">{{ notice }}</AimaFeedbackBanner>

      <div class="runtime-rule">
        <strong>什么时候生效</strong>
        <span>保存后只影响新建任务；已经创建或正在运行的任务继续使用原配置，不会被中途改变。</span>
      </div>

      <div v-if="loading" class="empty-state">正在读取配置…</div>
      <div v-else-if="items.length === 0" class="empty-state">尚未创建{{ isLlm ? ' AI 模型' : ' TikHub' }}配置。填写右侧信息后即可使用。</div>
      <button v-for="item in items" v-else :key="item.id" type="button" class="provider-item" :class="{ active: selectedId === item.id }" @click="selectItem(item)">
        <span class="provider-item__head"><strong>{{ item.display_name }}</strong><span class="badges"><em v-if="item.is_default">默认</em><em :class="{ muted: !item.enabled }">{{ item.enabled ? '已启用' : '已停用' }}</em></span></span>
        <span v-if="item.model">模型：{{ item.model }}</span>
        <small>{{ item.secret_configured ? '访问密钥已配置' : '访问密钥未配置' }}</small>
      </button>

      <details class="archived-list" @toggle="onArchivedToggle">
        <summary>已归档配置</summary>
        <div v-if="archivedLoading" class="archived-state">正在读取…</div>
        <div v-else-if="archivedItems.length === 0" class="archived-state">暂无已归档配置。</div>
        <div v-for="item in archivedItems" v-else :key="item.id" class="archived-item">
          <span><strong>{{ item.name }}</strong><small>{{ formatDateTime(item.archived_at) }}</small></span>
          <AimaButton variant="text" size="small" :disabled="saving" @click="restoreArchived(item)">恢复</AimaButton>
          <AimaButton variant="text" size="small" :disabled="saving" @click="permanentlyDelete(item)">永久删除</AimaButton>
        </div>
      </details>
    </section>

    <section class="card provider-form">
      <header><div><h2>{{ draft.id ? '编辑服务配置' : '新增服务配置' }}</h2><p>访问密钥不会回显。编辑已有配置时留空表示继续使用当前密钥。</p></div></header>

      <div class="form-grid">
        <label><span>配置名称</span><input v-model="draft.displayName" placeholder="例如：默认 AI 模型"></label>
        <label v-if="isLlm"><span>模型标识</span><input v-model="draft.model" placeholder="填写服务商提供的模型标识"></label>
        <label class="span-2"><span>服务地址</span><input v-model="draft.baseUrl" :placeholder="isLlm ? 'https://provider.example/v1' : 'https://api.tikhub.dev'"></label>
        <label class="span-2"><span>访问密钥</span><input v-model="draft.apiKey" type="password" autocomplete="new-password" :placeholder="draft.id ? '留空表示保持不变' : '创建配置时必填'"><small v-if="draft.id">为安全起见，系统不会把当前密钥返回到浏览器。</small></label>
      </div>

      <details class="advanced-settings">
        <summary>高级设置</summary>
        <p>通常保持默认值即可；只有服务商限流、响应较慢或需要控制并发时才需要调整。</p>
        <div class="advanced-grid">
          <label><span>单次请求最长等待时间（秒）</span><input v-model.number="draft.timeoutSeconds" type="number" min="1" max="3600"></label>
          <label><span>{{ isLlm ? '结果校验失败重试次数' : '请求失败重试次数' }}</span><input v-model.number="draft.maxRetries" type="number" min="0" max="20"><small v-if="isLlm">仅在模型返回结果不符合系统要求时重试。</small></label>
          <label><span>同时请求数上限</span><input v-model.number="draft.maxConcurrency" type="number" min="1" max="5000"><small>控制同一时间最多发起多少个请求；系统会据此自动安排任务分片。</small></label>
          <label><span>每秒请求启动上限</span><input v-model="draft.maxRps" type="number" min="1" max="10000" placeholder="留空表示不额外限速"><small>服务商存在每秒请求限制时填写；留空表示不额外限速。</small></label>
        </div>
      </details>

      <div class="switches">
        <label class="check-row"><input v-model="draft.enabled" type="checkbox"><span><strong>启用配置</strong><small>停用后，新任务不会再选择这项配置。</small></span></label>
        <label v-if="isLlm" class="check-row"><input v-model="draft.isDefault" type="checkbox"><span><strong>设为默认 AI 模型</strong><small>没有特别指定时，新 AI 分析任务使用这项配置。</small></span></label>
      </div>

      <div class="security-note"><strong>密钥保护</strong><span>访问密钥不会在页面、审计记录或运行日志中显示明文；更新密钥也不会影响已经开始执行的任务。</span></div>

      <AimaFeedbackBanner v-if="connectionResult" :tone="connectionResult.ok ? 'success' : 'warning'" role="status">
        <strong>{{ connectionResult.ok ? '连接测试通过' : '连接测试未通过' }}</strong>
        <span>{{ connectionResult.message }}</span>
        <small v-if="connectionResult.latency_ms != null">耗时 {{ connectionResult.latency_ms }} 毫秒</small>
      </AimaFeedbackBanner>

      <details class="technical-details">
        <summary>技术信息</summary>
        <dl>
          <div><dt>服务类型标识</dt><dd><input v-model="draft.provider" :readonly="Boolean(draft.id) || !isLlm" :placeholder="isLlm ? 'openai_compatible' : 'tikhub'"></dd></div>
          <div v-if="selectedItem"><dt>配置标识</dt><dd>{{ selectedItem.id }}</dd></div>
          <div v-if="selectedItem"><dt>配置修订号</dt><dd>{{ selectedItem.revision }}</dd></div>
        </dl>
      </details>

      <div class="actions">
        <AimaButton :disabled="saving" @click="resetDraft()">重置</AimaButton>
        <AimaButton v-if="draft.id" :disabled="saving || testing" @click="testConnection">{{ testing ? '测试中…' : '测试连接' }}</AimaButton>
        <AimaButton v-if="draft.id" :disabled="saving || testing" @click="archiveCurrent">归档</AimaButton>
        <AimaButton variant="primary" :disabled="saving || !formValid" @click="save">{{ saving ? '保存中…' : '保存并生效' }}</AimaButton>
      </div>
    </section>
  </div>
</template>

<style scoped>
.provider-layout { display: grid; grid-template-columns: minmax(280px, .78fr) minmax(0, 1.55fr); gap: 12px; }
.card { min-width: 0; padding: 16px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); background: var(--aima-surface); }
.card > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
h2,p { margin: 0; } h2 { color: var(--aima-text); font-size: 15px; }.card p { margin-top: 4px; color: var(--aima-text-muted); font-size: 11px; line-height: 17px; }
.provider-list { display: grid; align-content: start; gap: 8px; }.runtime-rule,.security-note { display: grid; gap: 4px; padding: 11px 12px; border: 1px solid var(--aima-border); border-radius: 7px; background: #f8f9fb; }.runtime-rule strong,.security-note strong { color: var(--aima-text); font-size: 11px; }.runtime-rule span,.security-note span { color: var(--aima-text-muted); font-size: 11px; line-height: 17px; }
.provider-item { display: grid; gap: 5px; width: 100%; padding: 11px 12px; border: 1px solid var(--aima-border); border-radius: 7px; color: var(--aima-text-secondary); background: #fff; cursor: pointer; text-align: left; }.provider-item.active { border-color: var(--aima-primary); background: #fff7fa; }.provider-item__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }.provider-item strong { color: var(--aima-text); font-size: 12px; }.provider-item span,.provider-item small { font-size: 11px; }.provider-item small { color: var(--aima-text-disabled); }.badges { display: flex; gap: 4px; }.badges em { padding: 2px 5px; border-radius: 4px; color: var(--aima-primary); background: var(--aima-primary-soft); font-size: 9px; font-style: normal; }.badges em.muted { color: var(--aima-text-muted); background: #f0f2f5; }
.empty-state,.archived-state { padding: 24px 10px; color: var(--aima-text-muted); text-align: center; font-size: 11px; }.archived-list { margin-top: 4px; border: 1px solid var(--aima-border); border-radius: 7px; overflow: hidden; }.archived-list summary { padding: 10px 12px; cursor: pointer; color: var(--aima-text-secondary); font-size: 11px; font-weight: 600; }.archived-item { display: grid; grid-template-columns: minmax(0,1fr) auto auto; gap: 6px; align-items: center; padding: 9px 11px; border-top: 1px solid var(--aima-border); }.archived-item strong,.archived-item small { display: block; }.archived-item strong { color: var(--aima-text); font-size: 11px; }.archived-item small { margin-top: 2px; color: var(--aima-text-disabled); font-size: 9px; }
.provider-form { display: grid; align-content: start; gap: 14px; }.form-grid,.advanced-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.form-grid label,.advanced-grid label { display: grid; gap: 5px; color: var(--aima-text-muted); font-size: 11px; }.span-2 { grid-column: 1/-1; }.form-grid input,.advanced-grid input,.technical-details input { width: 100%; height: 38px; padding: 0 10px; border: 1px solid var(--aima-border-strong); border-radius: 6px; color: var(--aima-text-secondary); background: #fff; }.form-grid small,.advanced-grid small { color: var(--aima-text-disabled); font-size: 10px; line-height: 15px; }.advanced-settings,.technical-details { border: 1px solid var(--aima-border); border-radius: 7px; padding: 10px 12px; }.advanced-settings summary,.technical-details summary { cursor: pointer; color: var(--aima-text-secondary); font-size: 11px; font-weight: 600; }.advanced-settings p { margin: 5px 0 10px; }.advanced-grid { margin-top: 10px; }
.switches { display: grid; gap: 7px; }.check-row { display: flex; align-items: center; gap: 9px; }.check-row > input { width: 16px; height: 16px; accent-color: var(--aima-primary); }.check-row span { display: grid; gap: 2px; }.check-row strong { color: var(--aima-text); font-size: 11px; }.check-row small { color: var(--aima-text-muted); font-size: 10px; }.technical-details dl { display: grid; gap: 7px; margin: 10px 0 0; }.technical-details dl div { display: grid; grid-template-columns: 100px minmax(0,1fr); gap: 8px; }.technical-details dt { color: var(--aima-text-disabled); font-size: 10px; }.technical-details dd { margin: 0; overflow-wrap: anywhere; color: var(--aima-text-secondary); font-size: 11px; }
.actions { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }.actions :deep(.aima-button) { min-width: 86px; }
@media (max-width: 980px) { .provider-layout { grid-template-columns: 1fr; }.form-grid,.advanced-grid { grid-template-columns: 1fr; }.span-2 { grid-column: auto; } }
</style>