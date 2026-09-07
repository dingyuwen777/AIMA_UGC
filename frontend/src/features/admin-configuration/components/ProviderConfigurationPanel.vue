<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { apiErrorMessage } from '../../../shared/api/http'
import AimaButton from '../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../shared/ui/AimaFeedbackBanner.vue'
import {
  addProviderConfig,
  editProviderConfig,
  fetchProviderConfigs,
  type ProviderConfigCreateRequest,
  type ProviderConfigResponse,
  type ProviderConfigUpdateRequest,
} from '../api'

const props = defineProps<{
  providerKind: 'llm' | 'collection'
}>()

const items = ref<ProviderConfigResponse[]>([])
const selectedId = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)

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

onMounted(async () => {
  await load()
})

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    items.value = (await fetchProviderConfigs(props.providerKind)).items
    const selected = items.value.find((item) => item.id === selectedId.value)
      ?? items.value.find((item) => item.is_default)
      ?? items.value[0]
    if (selected) selectItem(selected)
    else resetDraft()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    loading.value = false
  }
}

function resetDraft(): void {
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
  error.value = null
  notice.value = null
}

function selectItem(item: ProviderConfigResponse): void {
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
  error.value = null
  notice.value = null
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
      const updated = await editProviderConfig(draft.id, body)
      notice.value = draft.apiKey.trim()
        ? '配置已保存，访问密钥已更新；新任务将使用新配置。'
        : '配置已保存；新任务将使用新配置，正在运行的任务不受影响。'
      await load()
      const refreshed = items.value.find((item) => item.id === updated.id)
      if (refreshed) selectItem(refreshed)
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
      const created = await addProviderConfig(body)
      notice.value = '配置已创建；新任务无需重启服务即可使用。'
      await load()
      const refreshed = items.value.find((item) => item.id === created.id)
      if (refreshed) selectItem(refreshed)
    }
    draft.apiKey = ''
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
        <AimaButton
          size="small"
          @click="resetDraft"
        >
          新增配置
        </AimaButton>
      </header>

      <AimaFeedbackBanner
        v-if="error"
        tone="error"
        role="alert"
      >
        {{ error }}
      </AimaFeedbackBanner>
      <AimaFeedbackBanner
        v-if="notice"
        tone="success"
      >
        {{ notice }}
      </AimaFeedbackBanner>

      <div class="runtime-rule">
        <strong>什么时候生效</strong>
        <span>保存后只影响新建任务；已经创建或正在运行的任务继续使用原配置，不会被中途改变。</span>
      </div>

      <div
        v-if="loading"
        class="empty-state"
      >
        正在读取配置…
      </div>
      <div
        v-else-if="items.length === 0"
        class="empty-state"
      >
        尚未创建{{ isLlm ? ' AI 模型' : ' TikHub' }}配置。填写右侧信息后即可使用。
      </div>
      <button
        v-for="item in items"
        v-else
        :key="item.id"
        type="button"
        class="provider-item"
        :class="{ active: selectedId === item.id }"
        @click="selectItem(item)"
      >
        <span class="provider-item__head">
          <strong>{{ item.display_name }}</strong>
          <span class="badges">
            <em v-if="item.is_default">默认</em>
            <em :class="{ muted: !item.enabled }">{{ item.enabled ? '已启用' : '已停用' }}</em>
          </span>
        </span>
        <span v-if="item.model">模型：{{ item.model }}</span>
        <small>{{ item.secret_configured ? '访问密钥已配置' : '访问密钥未配置' }}</small>
      </button>
    </section>

    <section class="card provider-form">
      <header>
        <div>
          <h2>{{ draft.id ? '编辑服务配置' : '新增服务配置' }}</h2>
          <p>访问密钥不会回显。编辑已有配置时留空表示继续使用当前密钥。</p>
        </div>
      </header>

      <div class="form-grid">
        <label>
          <span>配置名称</span>
          <input
            v-model="draft.displayName"
            placeholder="例如：默认 AI 模型"
          >
        </label>
        <label v-if="isLlm">
          <span>模型标识</span>
          <input
            v-model="draft.model"
            placeholder="填写服务商提供的模型标识"
          >
        </label>
        <label class="span-2">
          <span>服务地址</span>
          <input
            v-model="draft.baseUrl"
            :placeholder="isLlm ? 'https://provider.example/v1' : 'https://api.tikhub.dev'"
          >
        </label>
        <label class="span-2">
          <span>访问密钥</span>
          <input
            v-model="draft.apiKey"
            type="password"
            autocomplete="new-password"
            :placeholder="draft.id ? '留空表示保持不变' : '创建配置时必填'"
          >
          <small v-if="draft.id">为安全起见，系统不会把当前密钥返回到浏览器。</small>
        </label>
      </div>

      <details class="advanced-settings">
        <summary>高级设置</summary>
        <p>通常保持默认值即可；只有服务商限流、响应较慢或需要控制并发时才需要调整。</p>
        <div class="advanced-grid">
          <label>
            <span>单次请求最长等待时间（秒）</span>
            <input
              v-model.number="draft.timeoutSeconds"
              type="number"
              min="1"
              max="3600"
            >
          </label>
          <label>
            <span>{{ isLlm ? '结果校验失败重试次数' : '请求失败重试次数' }}</span>
            <input
              v-model.number="draft.maxRetries"
              type="number"
              min="0"
              max="20"
            >
            <small v-if="isLlm">仅在模型返回结果不符合系统要求时重试。</small>
          </label>
          <label>
            <span>同时请求数上限</span>
            <input
              v-model.number="draft.maxConcurrency"
              type="number"
              min="1"
              max="5000"
            >
            <small>控制同一时间最多发起多少个请求。</small>
          </label>
          <label>
            <span>每秒请求启动上限</span>
            <input
              v-model="draft.maxRps"
              type="number"
              min="1"
              max="10000"
              placeholder="留空表示不额外限速"
            >
            <small>服务商存在每秒请求限制时填写；留空表示不额外限速。</small>
          </label>
        </div>
      </details>

      <div class="switches">
        <label class="check-row">
          <input
            v-model="draft.enabled"
            type="checkbox"
          >
          <span><strong>启用配置</strong><small>停用后，新任务不会再选择这项配置。</small></span>
        </label>
        <label
          v-if="isLlm"
          class="check-row"
        >
          <input
            v-model="draft.isDefault"
            type="checkbox"
          >
          <span><strong>设为默认 AI 模型</strong><small>没有特别指定时，新 AI 分析任务使用这项配置。</small></span>
        </label>
      </div>

      <div class="security-note">
        <strong>密钥保护</strong>
        <span>访问密钥不会在页面、审计记录或运行日志中显示明文；更新密钥也不会影响已经开始执行的任务。</span>
      </div>

      <details class="technical-details">
        <summary>技术信息</summary>
        <dl>
          <div><dt>服务类型标识</dt><dd>
            <input
              v-model="draft.provider"
              :readonly="Boolean(draft.id) || !isLlm"
              :placeholder="isLlm ? 'openai_compatible' : 'tikhub'"
            >
          </dd></div>
          <div v-if="selectedItem"><dt>配置标识</dt><dd>{{ selectedItem.id }}</dd></div>
          <div v-if="selectedItem"><dt>配置修订号</dt><dd>{{ selectedItem.revision }}</dd></div>
        </dl>
      </details>

      <div class="actions">
        <AimaButton
          :disabled="saving"
          @click="resetDraft"
        >
          重置
        </AimaButton>
        <AimaButton
          variant="primary"
          :disabled="saving || !formValid"
          @click="save"
        >
          {{ saving ? '保存中…' : '保存并生效' }}
        </AimaButton>
      </div>
    </section>
  </div>
</template>

<style scoped>
.provider-layout { display: grid; grid-template-columns: minmax(280px, .78fr) minmax(0, 1.55fr); gap: 12px; }
.card { min-width: 0; padding: 16px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); background: var(--aima-surface); }
.card > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
h2, p { margin: 0; }
h2 { color: var(--aima-text); font-size: 15px; }
.card p { margin-top: 4px; color: var(--aima-text-muted); font-size: 11px; line-height: 17px; }
.provider-list { display: grid; align-content: start; gap: 8px; }
.runtime-rule,
.security-note { display: grid; gap: 4px; padding: 11px 12px; border: 1px solid var(--aima-border); border-radius: 7px; background: #f8f9fb; }
.runtime-rule strong,
.security-note strong { color: var(--aima-text-secondary); font-size: 11px; }
.runtime-rule span,
.security-note span { color: var(--aima-text-muted); font-size: 10px; line-height: 16px; }
.provider-item { display: grid; gap: 5px; width: 100%; padding: 11px 12px; border: 1px solid var(--aima-border); border-radius: 7px; color: var(--aima-text-secondary); background: var(--aima-surface); cursor: pointer; text-align: left; }
.provider-item.active { border-color: var(--aima-primary); background: var(--aima-primary-soft); }
.provider-item__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.provider-item strong { font-size: 12px; }
.provider-item > span:not(.provider-item__head) { color: var(--aima-text-muted); font-size: 10px; }
.provider-item small { color: var(--aima-text-disabled); font-size: 10px; }
.badges { display: flex; gap: 4px; }
.badges em { padding: 2px 5px; border-radius: 4px; color: var(--aima-primary); background: var(--aima-primary-soft); font-size: 9px; font-style: normal; }
.badges em.muted { color: var(--aima-text-muted); background: #f2f4f7; }
.empty-state { padding: 28px 14px; color: var(--aima-text-muted); background: #fafbfc; text-align: center; font-size: 11px; line-height: 18px; }
.provider-form { display: grid; align-content: start; gap: 14px; }
.form-grid,
.advanced-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.form-grid label,
.advanced-grid label { display: grid; gap: 6px; color: var(--aima-text-muted); font-size: 11px; }
.form-grid label > small,
.advanced-grid label > small { color: var(--aima-text-disabled); font-size: 10px; line-height: 15px; }
.span-2 { grid-column: span 2; }
input { width: 100%; height: 38px; box-sizing: border-box; padding: 8px 10px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-control); outline: none; color: var(--aima-text-secondary); background: var(--aima-surface); font: inherit; font-size: 12px; }
input:read-only { cursor: not-allowed; color: var(--aima-text-muted); background: #f5f7fa; }
input:focus { border-color: var(--aima-primary); box-shadow: 0 0 0 2px var(--aima-primary-soft); }
.advanced-settings,
.technical-details { border: 1px solid var(--aima-border); border-radius: 7px; background: #fafbfc; }
.advanced-settings > summary,
.technical-details > summary { padding: 10px 12px; color: var(--aima-text-secondary); cursor: pointer; font-size: 11px; font-weight: 600; }
.advanced-settings > p { margin: 0; padding: 0 12px 10px; }
.advanced-grid { padding: 0 12px 12px; }
.technical-details dl { display: grid; gap: 8px; margin: 0; padding: 0 12px 12px; }
.technical-details dl > div { display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 12px; align-items: center; }
.technical-details dt { color: var(--aima-text-muted); font-size: 10px; }
.technical-details dd { min-width: 0; margin: 0; overflow-wrap: anywhere; color: var(--aima-text-secondary); font-size: 10px; }
.switches { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.check-row { display: flex; align-items: flex-start; gap: 9px; padding: 10px 12px; border: 1px solid var(--aima-border); border-radius: 7px; }
.check-row > input { flex: 0 0 auto; width: 15px; height: 15px; margin-top: 2px; }
.check-row > span { display: grid; gap: 2px; }
.check-row strong { color: var(--aima-text-secondary); font-size: 11px; }
.check-row small { color: var(--aima-text-muted); font-size: 10px; line-height: 15px; }
.actions { display: flex; justify-content: flex-end; gap: 8px; }
@media (max-width: 1280px) { .provider-layout { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .form-grid, .advanced-grid, .switches { grid-template-columns: 1fr; } .span-2 { grid-column: auto; } }
</style>
