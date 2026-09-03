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
const panelTitle = computed(() => (isLlm.value ? 'AI 模型运行配置' : 'TikHub 运行配置'))
const panelDescription = computed(() => (
  isLlm.value
    ? '配置 OpenAI-compatible 模型连接、模型名和运行参数。默认配置会被新建 Analysis Run 立即读取。'
    : '配置 TikHub 连接与请求限制。采集 Run 创建后会冻结对应 Provider 版本，后续修改只影响新 Run。'
))
const formValid = computed(() => {
  if (!draft.displayName.trim() || !draft.provider.trim() || !draft.baseUrl.trim()) return false
  if (isLlm.value && !draft.model.trim()) return false
  if (!draft.id && !draft.apiKey.trim()) return false
  return draft.timeoutSeconds > 0
    && draft.maxRetries >= 0
    && draft.maxConcurrency > 0
    && (!draft.maxRps || Number(draft.maxRps) > 0)
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
        ? '配置已保存，密钥已轮换为新的不可变版本；新任务立即使用新配置。'
        : '配置已保存；新任务立即使用新配置，当前运行任务保持原快照。'
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
      notice.value = '配置已创建并写入 Secret Store；新任务无需重启服务即可使用。'
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
        <strong>生效规则</strong>
        <span>保存后，新建任务读取最新配置；已创建/运行中的任务及其自动重试继续使用原运行时快照。</span>
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
        尚未创建{{ isLlm ? ' AI 模型' : ' TikHub' }}配置。右侧填写后即可启用运行时配置中心。
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
            <em :class="{ muted: !item.enabled }">{{ item.enabled ? '启用' : '停用' }}</em>
          </span>
        </span>
        <span>{{ item.provider }}<template v-if="item.model"> · {{ item.model }}</template></span>
        <small>revision {{ item.revision }} · {{ item.secret_configured ? '密钥已配置' : '密钥未配置' }}</small>
      </button>
    </section>

    <section class="card provider-form">
      <header>
        <div>
          <h2>{{ draft.id ? '编辑运行配置' : '新增运行配置' }}</h2>
          <p>API Key 不会回显。编辑时留空表示沿用当前密钥；填写新值会创建新的不可变 Secret 版本。</p>
        </div>
      </header>

      <div class="form-grid">
        <label>
          <span>配置名称</span>
          <input
            v-model="draft.displayName"
            placeholder="便于管理员识别"
          >
        </label>
        <label>
          <span>Provider 标识</span>
          <input
            v-model="draft.provider"
            :readonly="Boolean(draft.id) || !isLlm"
            :placeholder="isLlm ? 'openai_compatible' : 'tikhub'"
          >
          <small>稳定身份创建后不可修改。平台类型与 Provider 是两个不同概念。</small>
        </label>
        <label class="span-2">
          <span>Base URL</span>
          <input
            v-model="draft.baseUrl"
            :placeholder="isLlm ? 'https://provider.example/v1' : 'https://api.tikhub.dev'"
          >
        </label>
        <label v-if="isLlm">
          <span>模型</span>
          <input
            v-model="draft.model"
            placeholder="例如 provider 的正式 model id"
          >
        </label>
        <label :class="{ 'span-2': !isLlm }">
          <span>API Key</span>
          <input
            v-model="draft.apiKey"
            type="password"
            autocomplete="new-password"
            :placeholder="draft.id ? '留空保持当前密钥' : '创建配置时必填'"
          >
          <small v-if="draft.id">当前密钥不会从后端返回到浏览器。</small>
        </label>
        <label>
          <span>请求超时（秒）</span>
          <input
            v-model.number="draft.timeoutSeconds"
            type="number"
            min="1"
            max="3600"
          >
        </label>
        <label>
          <span>最大重试/校验次数</span>
          <input
            v-model.number="draft.maxRetries"
            type="number"
            min="0"
            max="20"
          >
        </label>
        <label>
          <span>最大并发</span>
          <input
            v-model.number="draft.maxConcurrency"
            type="number"
            min="1"
            max="500"
          >
        </label>
        <label>
          <span>最大 RPS</span>
          <input
            v-model="draft.maxRps"
            type="number"
            min="1"
            max="10000"
            placeholder="留空表示不额外限速"
          >
        </label>
      </div>

      <div class="switches">
        <label class="check-row">
          <input
            v-model="draft.enabled"
            type="checkbox"
          >
          <span><strong>启用配置</strong><small>停用后不会被新的运行选择。</small></span>
        </label>
        <label
          v-if="isLlm"
          class="check-row"
        >
          <input
            v-model="draft.isDefault"
            type="checkbox"
          >
          <span><strong>设为默认 AI 模型</strong><small>新 Analysis Run 只读取启用的默认 LLM 配置。</small></span>
        </label>
      </div>

      <div class="security-note">
        <strong>密钥边界</strong>
        <span>数据库、接口响应、审计和运行日志都不保存 API Key 明文。Run 仅冻结不可变 Secret 引用，确保密钥轮换后旧任务仍可安全重试。</span>
      </div>

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
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.form-grid label { display: grid; gap: 6px; color: var(--aima-text-muted); font-size: 11px; }
.form-grid label > small { color: var(--aima-text-disabled); font-size: 10px; line-height: 15px; }
.span-2 { grid-column: span 2; }
input { width: 100%; height: 38px; box-sizing: border-box; padding: 8px 10px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-control); outline: none; color: var(--aima-text-secondary); background: var(--aima-surface); font: inherit; font-size: 12px; }
input:read-only { cursor: not-allowed; color: var(--aima-text-muted); background: #f5f7fa; }
input:focus { border-color: var(--aima-primary); box-shadow: 0 0 0 2px var(--aima-primary-soft); }
.switches { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.check-row { display: flex; align-items: flex-start; gap: 9px; padding: 10px 12px; border: 1px solid var(--aima-border); border-radius: 7px; }
.check-row > input { flex: 0 0 auto; width: 15px; height: 15px; margin-top: 2px; }
.check-row > span { display: grid; gap: 2px; }
.check-row strong { color: var(--aima-text-secondary); font-size: 11px; }
.check-row small { color: var(--aima-text-muted); font-size: 10px; line-height: 15px; }
.actions { display: flex; justify-content: flex-end; gap: 8px; }
@media (max-width: 1280px) { .provider-layout { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .form-grid, .switches { grid-template-columns: 1fr; } .span-2 { grid-column: auto; } }
</style>
