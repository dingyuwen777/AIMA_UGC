<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import type {
  AnalysisSchemeDefinitionRequest,
  AnalysisSchemeResponse,
  AnalysisSchemeVersionResponse,
  AuditEventResponse,
  KeywordPackSummaryResponse,
  ResourceLifecycleResponse,
  VehicleModelResponse,
} from '../../../generated/api/client'
import AppShell from '../../../app/layouts/AppShell.vue'
import { apiErrorMessage } from '../../../shared/api/http'
import { formatDateTime } from '../../../shared/domain/beijingTime'
import AimaButton from '../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../shared/ui/AimaFeedbackBanner.vue'
import AimaPageHeader from '../../../shared/ui/AimaPageHeader.vue'
import VehicleMultiSelect from '../../../shared/VehicleMultiSelect.vue'
import {
  activateScheme,
  addSchemeDraft,
  addVehicle,
  archiveScheme,
  copyScheme,
  deleteArchivedScheme,
  editSchemeDraft,
  editVehicle,
  fetchArchivedSchemes,
  fetchAuditEvents,
  fetchKeywordPacksForAdmin,
  fetchSchemeDeleteEligibility,
  fetchSchemes,
  fetchVehicles,
  mergeVehicle,
  removeVehicle,
  restoreArchivedScheme,
  restoreScheme,
  saveKeywordPackVehicles,
} from '../api'
import AnalysisLabelsEditor from '../components/AnalysisLabelsEditor.vue'
import ProviderConfigurationPanel from '../components/ProviderConfigurationPanel.vue'
import {
  auditActionLabel,
  auditActorLabel,
  auditObjectLabel,
  auditSummaryText,
  formatRuntimeStatus,
} from '../presentation'

type Tab = 'vehicles' | 'links' | 'llm' | 'tikhub' | 'scheme' | 'audit'

const tab = ref<Tab>('vehicles')
const saving = ref(false)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)
const vehicles = ref<VehicleModelResponse[]>([])
const packs = ref<KeywordPackSummaryResponse[]>([])
const schemes = ref<AnalysisSchemeResponse[]>([])
const archivedSchemes = ref<ResourceLifecycleResponse[]>([])
const auditEvents = ref<AuditEventResponse[]>([])
const selectedPackId = ref('')
const linkedVehicleIds = ref<string[]>([])
const selectedSchemeVersionId = ref('')
const vehicleLoading = ref(false)
const packLoading = ref(false)
const schemeLoading = ref(false)
const archivedSchemeLoading = ref(false)
const schemeLabelsValid = ref(true)
const schemeCopyName = ref('')
const auditLoading = ref(false)
const vehicleError = ref<string | null>(null)
const packError = ref<string | null>(null)
const schemeError = ref<string | null>(null)
const auditError = ref<string | null>(null)
const auditTotal = ref(0)
const auditOffset = ref(0)
const auditLimit = 100

const vehicleDraft = reactive({ id: '', code: '', displayName: '', aliases: '', status: 'active' as 'active' | 'deprecated' })
const mergeTargetId = ref('')
const schemeDraft = reactive({
  schemeName: '',
  description: '',
  promptTemplate: '',
  voiceTypes: '',
  sentiments: '',
  labelsJson: '{}',
})

const vehicleFormValid = computed(() => Boolean(
  vehicleDraft.code.trim() && vehicleDraft.displayName.trim(),
))
const loading = computed(() => {
  if (tab.value === 'vehicles') return vehicleLoading.value
  if (tab.value === 'links') return vehicleLoading.value || packLoading.value
  if (tab.value === 'scheme') return schemeLoading.value
  if (tab.value === 'llm' || tab.value === 'tikhub') return false
  return auditLoading.value
})
const activeResourceError = computed(() => {
  if (tab.value === 'vehicles') return vehicleError.value
  if (tab.value === 'links') return packError.value ?? vehicleError.value
  if (tab.value === 'scheme') return schemeError.value
  if (tab.value === 'llm' || tab.value === 'tikhub') return null
  return auditError.value
})
const selectedPack = computed(() => packs.value.find((item) => item.id === selectedPackId.value) ?? null)
const selectedSchemeVersion = computed(() => {
  for (const scheme of schemes.value) {
    const version = scheme.versions.find((item) => item.id === selectedSchemeVersionId.value)
    if (version) return { scheme, version }
  }
  return null
})

onMounted(refreshAll)

async function loadVehicles(): Promise<void> {
  vehicleLoading.value = true
  vehicleError.value = null
  try {
    vehicles.value = (await fetchVehicles()).items
    if (selectedPackId.value) selectPack(selectedPackId.value)
  } catch (reason) {
    vehicleError.value = apiErrorMessage(reason)
  } finally {
    vehicleLoading.value = false
  }
}

async function loadPacks(): Promise<void> {
  packLoading.value = true
  packError.value = null
  try {
    packs.value = (await fetchKeywordPacksForAdmin()).items
    if (!packs.value.some((item) => item.id === selectedPackId.value)) {
      selectedPackId.value = packs.value[0]?.id ?? ''
    }
    if (selectedPackId.value) selectPack(selectedPackId.value)
  } catch (reason) {
    packError.value = apiErrorMessage(reason)
  } finally {
    packLoading.value = false
  }
}

async function loadSchemes(): Promise<void> {
  schemeLoading.value = true
  schemeError.value = null
  try {
    schemes.value = (await fetchSchemes()).items
    const knownVersion = schemes.value
      .flatMap((item) => item.versions)
      .some((item) => item.id === selectedSchemeVersionId.value)
    if (!knownVersion) {
      const initial = schemes.value.flatMap((item) => item.versions).find((item) => item.status === 'draft')
        ?? schemes.value.flatMap((item) => item.versions)[0]
      selectedSchemeVersionId.value = initial?.id ?? ''
      if (initial) selectSchemeVersion(initial.id)
    }
  } catch (reason) {
    schemeError.value = apiErrorMessage(reason)
  } finally {
    schemeLoading.value = false
  }
}

async function loadArchivedSchemes(): Promise<void> {
  archivedSchemeLoading.value = true
  schemeError.value = null
  try {
    archivedSchemes.value = (await fetchArchivedSchemes()).items
  } catch (reason) {
    schemeError.value = apiErrorMessage(reason)
  } finally {
    archivedSchemeLoading.value = false
  }
}

function onArchivedSchemesToggle(event: Event): void {
  if ((event.currentTarget as HTMLDetailsElement).open) void loadArchivedSchemes()
}

async function loadAudit(): Promise<void> {
  auditLoading.value = true
  auditError.value = null
  try {
    const response = await fetchAuditEvents(auditOffset.value, auditLimit)
    auditEvents.value = response.items
    auditTotal.value = response.total
    if (auditOffset.value >= response.total && auditOffset.value > 0) {
      auditOffset.value = Math.max(0, Math.floor(Math.max(0, response.total - 1) / auditLimit) * auditLimit)
      const corrected = await fetchAuditEvents(auditOffset.value, auditLimit)
      auditEvents.value = corrected.items
      auditTotal.value = corrected.total
    }
  } catch (reason) {
    auditError.value = apiErrorMessage(reason)
  } finally {
    auditLoading.value = false
  }
}

async function refreshAll(): Promise<void> {
  await Promise.all([loadVehicles(), loadPacks(), loadSchemes(), loadAudit()])
}

async function retryActiveResource(): Promise<void> {
  if (tab.value === 'vehicles') return loadVehicles()
  if (tab.value === 'links') {
    await Promise.all([loadVehicles(), loadPacks()])
    return
  }
  if (tab.value === 'scheme') return loadSchemes()
  if (tab.value === 'llm' || tab.value === 'tikhub') return
  await loadAudit()
}

async function previousAuditPage(): Promise<void> {
  auditOffset.value = Math.max(0, auditOffset.value - auditLimit)
  await loadAudit()
}

async function nextAuditPage(): Promise<void> {
  if (auditOffset.value + auditLimit >= auditTotal.value) return
  auditOffset.value += auditLimit
  await loadAudit()
}

function splitLines(value: string): string[] {
  return [...new Set(value.split(/[\n,，]/).map((item) => item.trim()).filter(Boolean))]
}

function resetVehicleDraft(): void {
  Object.assign(vehicleDraft, { id: '', code: '', displayName: '', aliases: '', status: 'active' })
  mergeTargetId.value = ''
}

function editVehicleDraft(item: VehicleModelResponse): void {
  Object.assign(vehicleDraft, {
    id: item.id,
    code: item.code,
    displayName: item.display_name,
    aliases: (item.aliases ?? []).map((alias) => alias.text).join('\n'),
    status: item.status === 'deprecated' ? 'deprecated' : 'active',
  })
}

async function saveVehicle(): Promise<void> {
  if (!vehicleDraft.code.trim() || !vehicleDraft.displayName.trim()) return
  saving.value = true
  error.value = null
  try {
    if (vehicleDraft.id) {
      await editVehicle(vehicleDraft.id, {
        display_name: vehicleDraft.displayName,
        aliases: splitLines(vehicleDraft.aliases),
        status: vehicleDraft.status,
      })
    } else {
      await addVehicle({
        code: vehicleDraft.code,
        display_name: vehicleDraft.displayName,
        aliases: splitLines(vehicleDraft.aliases),
      })
    }
    notice.value = vehicleDraft.id ? '车型已更新并记录操作。' : '车型已创建并记录操作。'
    resetVehicleDraft()
    await refreshAll()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

async function deleteVehicle(item: VehicleModelResponse): Promise<void> {
  if (item.referenced) {
    error.value = '该车型已被业务数据引用，不能直接删除；请停用、改名或合并。'
    return
  }
  if (!window.confirm(`确定删除未引用车型“${item.display_name}”吗？系统会保留本次操作记录。`)) return
  try {
    await removeVehicle(item.id)
    notice.value = '未引用车型已删除并记录操作。'
    await refreshAll()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  }
}

async function mergeSelectedVehicle(): Promise<void> {
  if (!vehicleDraft.id || !mergeTargetId.value) return
  if (!window.confirm('合并后历史数据仍会保留，后续选择会统一到目标车型。是否继续？')) return
  try {
    await mergeVehicle(vehicleDraft.id, { target_vehicle_model_id: mergeTargetId.value })
    notice.value = '车型已合并并记录操作。'
    resetVehicleDraft()
    await refreshAll()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  }
}

function selectPack(packId: string): void {
  selectedPackId.value = packId
  linkedVehicleIds.value = vehicles.value
    .filter((item) => (item.keyword_pack_ids ?? []).includes(packId))
    .map((item) => item.id)
}

async function savePackLinks(): Promise<void> {
  if (!selectedPack.value) return
  saving.value = true
  try {
    await saveKeywordPackVehicles(selectedPack.value.id, linkedVehicleIds.value)
    notice.value = '词包与车型关联已更新并记录操作。'
    await refreshAll()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

function selectSchemeVersion(versionId: string): void {
  selectedSchemeVersionId.value = versionId
  const selection = schemes.value
    .flatMap((scheme) => scheme.versions.map((version) => ({ scheme, version })))
    .find((item) => item.version.id === versionId)
  if (!selection) return
  const { scheme, version } = selection
  Object.assign(schemeDraft, {
    schemeName: scheme.name,
    description: version.description,
    promptTemplate: version.definition.prompt_template,
    voiceTypes: version.definition.voice_types.join('\n'),
    sentiments: version.definition.sentiments.join('\n'),
    labelsJson: JSON.stringify(version.definition.labels, null, 2),
  })
}

function schemeDefinition(): AnalysisSchemeDefinitionRequest {
  const labels = JSON.parse(schemeDraft.labelsJson) as Record<string, string[]>
  return {
    prompt_template: schemeDraft.promptTemplate,
    voice_types: splitLines(schemeDraft.voiceTypes),
    sentiments: splitLines(schemeDraft.sentiments),
    labels,
  }
}

function validateSchemeDefinition(definition: AnalysisSchemeDefinitionRequest): void {
  if (!schemeLabelsValid.value) throw new Error('请先修正结构化标签规则。')
  if (!definition.prompt_template.includes('{{AIMA_TAXONOMY_JSON}}')) {
    throw new Error('提示词模板必须包含标签规则占位符 {{AIMA_TAXONOMY_JSON}}。')
  }
  if (!definition.voice_types.length || !definition.sentiments.length || !Object.keys(definition.labels).length) {
    throw new Error('发声类型、情感和标签都不能为空。')
  }
}

async function saveSchemeDraft(): Promise<void> {
  saving.value = true
  error.value = null
  try {
    const definition = schemeDefinition()
    validateSchemeDefinition(definition)
    const selected = selectedSchemeVersion.value
    let saved: AnalysisSchemeResponse
    if (selected?.version.status === 'draft') {
      saved = await editSchemeDraft(selected.version.id, {
        expected_version: selected.version.version,
        description: schemeDraft.description,
        definition,
      })
    } else {
      saved = await addSchemeDraft({
        name: schemeDraft.schemeName || `${selected?.scheme.name ?? 'AI 分析规则'} 草稿`,
        description: schemeDraft.description,
        definition,
      })
    }
    selectedSchemeVersionId.value = saved.versions.find((item) => item.status === 'draft')?.id ?? ''
    notice.value = 'AI 分析规则草稿已保存并记录操作。'
    await refreshAll()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

function startSchemeCopy(): void {
  const selected = selectedSchemeVersion.value
  if (!selected) return
  schemeCopyName.value = `${selected.scheme.name} 副本`
}

async function copySelectedScheme(): Promise<void> {
  const selected = selectedSchemeVersion.value
  if (!selected || !schemeCopyName.value.trim()) return
  saving.value = true
  error.value = null
  try {
    const copied = await copyScheme(selected.scheme.id, { name: schemeCopyName.value.trim() })
    schemeCopyName.value = ''
    await loadSchemes()
    const draft = copied.versions.find((item) => item.status === 'draft') ?? copied.versions[0]
    if (draft) selectSchemeVersion(draft.id)
    notice.value = 'AI 分析规则副本已创建为草稿。'
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

async function archiveSelectedScheme(): Promise<void> {
  const selected = selectedSchemeVersion.value
  if (!selected) return
  if (!window.confirm(`确认归档 AI 分析规则“${selected.scheme.name}”吗？当前生效规则会被服务端阻止归档，历史版本和历史分析任务不会被删除。`)) return
  saving.value = true
  error.value = null
  try {
    await archiveScheme(selected.scheme.id)
    selectedSchemeVersionId.value = ''
    await Promise.all([loadSchemes(), loadArchivedSchemes()])
    notice.value = 'AI 分析规则已归档。'
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

async function restoreArchivedAnalysisScheme(item: ResourceLifecycleResponse): Promise<void> {
  saving.value = true
  error.value = null
  try {
    await restoreArchivedScheme(item.id)
    await Promise.all([loadSchemes(), loadArchivedSchemes()])
    const restored = schemes.value.find((scheme) => scheme.id === item.id)
    const version = restored?.versions.find((entry) => entry.status === 'draft') ?? restored?.versions[0]
    if (version) selectSchemeVersion(version.id)
    notice.value = 'AI 分析规则已恢复；恢复后不会自动发布或生效。'
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

async function deleteArchivedAnalysisScheme(item: ResourceLifecycleResponse): Promise<void> {
  saving.value = true
  error.value = null
  try {
    const eligibility = await fetchSchemeDeleteEligibility(item.id)
    if (!eligibility.eligible) {
      error.value = (eligibility.blocking_reasons ?? []).join('；') || '该分析规则已有发布或运行历史，只能保留归档记录。'
      return
    }
    if (!window.confirm(`确认永久删除已归档 AI 分析规则“${item.name}”吗？只有从未发布、从未被分析任务使用的纯草稿规则才允许删除。`)) return
    await deleteArchivedScheme(item.id)
    await loadArchivedSchemes()
    notice.value = '未发布且未使用的归档 AI 分析规则已永久删除。'
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

async function publishVersion(version: AnalysisSchemeVersionResponse): Promise<void> {
  if (!window.confirm('发布后，新建的 AI 分析任务会使用此版本；正在运行的任务不受影响。是否发布？')) return
  try {
    await activateScheme(version.id, version.version)
    notice.value = 'AI 分析规则已发布并记录操作。'
    await refreshAll()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  }
}

async function rollbackVersion(version: AnalysisSchemeVersionResponse): Promise<void> {
  if (!window.confirm(`确认恢复到版本 ${version.version}？系统会完整记录本次操作。`)) return
  try {
    await restoreScheme(version.id, version.version)
    notice.value = `已恢复到版本 ${version.version} 并记录操作。`
    await refreshAll()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  }
}

function safeJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2)
}
</script>

<template>
  <AppShell section-title="管理员配置">
    <div class="admin-page">
      <AimaPageHeader
        title="管理员配置"
        description="统一管理车型、词包、AI 模型、采集服务和 AI 分析规则。技术标识与原始审计数据仅在需要时展开查看。"
      />
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

      <nav
        class="tabs"
        aria-label="管理员配置分类"
      >
        <button
          v-for="item in ([['vehicles', '车型管理'], ['links', '词包关联'], ['llm', 'AI 模型'], ['tikhub', 'TikHub'], ['scheme', 'AI 分析规则'], ['audit', '操作记录']] as const)"
          :key="item[0]"
          type="button"
          :class="{ active: tab === item[0] }"
          @click="tab = item[0]"
        >
          {{ item[1] }}
        </button>
      </nav>

      <AimaFeedbackBanner
        v-if="activeResourceError"
        tone="error"
        role="alert"
      >
        <strong>当前数据加载失败</strong>
        <span>{{ activeResourceError }}</span>
        <button
          class="retry-link"
          type="button"
          :disabled="loading"
          @click="retryActiveResource"
        >
          {{ loading ? '重试中…' : '重试当前数据' }}
        </button>
      </AimaFeedbackBanner>

      <section
        v-if="loading"
        class="state-card"
      >
        正在加载管理员配置…
      </section>

      <div
        v-else-if="tab === 'vehicles'"
        class="two-column"
      >
        <section class="card">
          <header>
            <div>
              <h2>车型目录</h2>
              <p>车型编码创建后保持不变；已被业务数据引用的车型只能停用、改名或合并。</p>
            </div>
            <AimaButton
              size="small"
              @click="resetVehicleDraft"
            >
              新增车型
            </AimaButton>
          </header>
          <table>
            <thead>
              <tr>
                <th>车型</th>
                <th>别名</th>
                <th>状态</th>
                <th>使用情况</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in vehicles"
                :key="item.id"
              >
                <td>
                  <strong>{{ item.display_name }}</strong>
                  <small>编码 {{ item.code }}</small>
                </td>
                <td>{{ (item.aliases ?? []).map((alias) => alias.text).join('、') || '—' }}</td>
                <td>
                  <span
                    class="status"
                    :class="`status--${item.status}`"
                  >
                    {{ formatRuntimeStatus(item.status) }}
                  </span>
                </td>
                <td>{{ item.referenced ? '已被使用' : '暂未使用' }}</td>
                <td>
                  <button
                    type="button"
                    @click="editVehicleDraft(item)"
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    :disabled="item.status === 'merged'"
                    @click="deleteVehicle(item)"
                  >
                    删除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
        <section class="card form-card">
          <h2>{{ vehicleDraft.id ? '编辑车型' : '新增车型' }}</h2>
          <label>
            车型编码
            <input
              v-model="vehicleDraft.code"
              :disabled="Boolean(vehicleDraft.id)"
              placeholder="例如 AIMA-Q7"
            >
            <small>用于稳定识别车型，创建后不可修改。</small>
          </label>
          <label>
            显示名称
            <input
              v-model="vehicleDraft.displayName"
              placeholder="例如 爱玛 Q7"
            >
          </label>
          <label>
            别名（每行一个）
            <textarea
              v-model="vehicleDraft.aliases"
              rows="6"
              placeholder="Q7&#10;爱玛Q7"
            />
          </label>
          <label v-if="vehicleDraft.id">
            状态
            <select v-model="vehicleDraft.status">
              <option value="active">
                正常使用
              </option>
              <option value="deprecated">
                停用
              </option>
            </select>
          </label>
          <div class="actions">
            <AimaButton @click="resetVehicleDraft">
              取消
            </AimaButton>
            <AimaButton
              variant="primary"
              :disabled="saving || !vehicleFormValid"
              @click="saveVehicle"
            >
              保存
            </AimaButton>
          </div>
          <template v-if="vehicleDraft.id">
            <hr>
            <h3>合并重复车型</h3>
            <select v-model="mergeTargetId">
              <option value="">
                选择目标车型
              </option>
              <option
                v-for="item in vehicles.filter((vehicle) => vehicle.id !== vehicleDraft.id && vehicle.status === 'active')"
                :key="item.id"
                :value="item.id"
              >
                {{ item.display_name }}（{{ item.code }}）
              </option>
            </select>
            <AimaButton
              :disabled="!mergeTargetId"
              @click="mergeSelectedVehicle"
            >
              合并到目标车型
            </AimaButton>
          </template>
        </section>
      </div>

      <div
        v-else-if="tab === 'links'"
        class="two-column"
      >
        <section class="card list-card">
          <h2>选择词包</h2>
          <button
            v-for="pack in packs"
            :key="pack.id"
            type="button"
            :class="{ active: selectedPackId === pack.id }"
            @click="selectPack(pack.id)"
          >
            <strong>{{ pack.name }}</strong>
            <span>版本 {{ pack.version }} · {{ pack.enabled ? '已启用' : '已停用' }}</span>
          </button>
        </section>
        <section class="card form-card">
          <h2>{{ selectedPack?.name ?? '词包车型关联' }}</h2>
          <p>选择这个词包适用的车型。多选车型时满足其中任一车型即可，随后再与词包关键词共同筛选。</p>
          <VehicleMultiSelect
            v-model="linkedVehicleIds"
            label="关联车型（可多选）"
          />
          <div class="actions">
            <AimaButton
              variant="primary"
              :disabled="!selectedPack || saving"
              @click="savePackLinks"
            >
              保存关联
            </AimaButton>
          </div>
        </section>
      </div>

      <div
        v-else-if="tab === 'scheme'"
        class="scheme-layout"
      >
        <section class="card list-card">
          <h2>版本历史</h2>
          <template
            v-for="scheme in schemes"
            :key="scheme.id"
          >
            <h3>{{ scheme.name }}</h3>
            <button
              v-for="version in scheme.versions"
              :key="version.id"
              type="button"
              :class="{ active: selectedSchemeVersionId === version.id }"
              @click="selectSchemeVersion(version.id)"
            >
              <strong>版本 {{ version.version }} · {{ formatRuntimeStatus(version.status) }}</strong>
              <span>{{ formatDateTime(version.created_at) }}</span>
            </button>
          </template>
          <details
            class="archived-schemes"
            @toggle="onArchivedSchemesToggle"
          >
            <summary>已归档规则</summary>
            <div
              v-if="archivedSchemeLoading"
              class="archived-scheme-state"
            >
              正在读取…
            </div>
            <div
              v-else-if="archivedSchemes.length === 0"
              class="archived-scheme-state"
            >
              暂无已归档规则。
            </div>
            <div
              v-for="item in archivedSchemes"
              v-else
              :key="item.id"
              class="archived-scheme-row"
            >
              <span><strong>{{ item.name }}</strong><small>{{ formatDateTime(item.archived_at) }}</small></span>
              <AimaButton
                variant="text"
                size="small"
                :disabled="saving"
                @click="restoreArchivedAnalysisScheme(item)"
              >
                恢复
              </AimaButton>
              <AimaButton
                variant="text"
                size="small"
                :disabled="saving"
                @click="deleteArchivedAnalysisScheme(item)"
              >
                永久删除
              </AimaButton>
            </div>
          </details>
        </section>
        <section class="card form-card scheme-editor">
          <header>
            <div>
              <h2>AI 分析规则</h2>
              <p>发声类型、情感和标签结构直接按业务含义维护；提示词仅在需要时进入高级设置。</p>
            </div>
            <span v-if="selectedSchemeVersion">
              {{ formatRuntimeStatus(selectedSchemeVersion.version.status) }}
            </span>
          </header>
          <div
            v-if="selectedSchemeVersion"
            class="scheme-resource-actions"
          >
            <AimaButton
              size="small"
              :disabled="saving"
              @click="startSchemeCopy"
            >
              复制规则
            </AimaButton>
            <AimaButton
              size="small"
              :disabled="saving"
              @click="archiveSelectedScheme"
            >
              归档规则
            </AimaButton>
          </div>
          <div
            v-if="schemeCopyName"
            class="scheme-copy-editor"
          >
            <label>副本名称<input
              v-model="schemeCopyName"
              maxlength="200"
            ></label>
            <small>复制的是该规则当前最新版本；副本只创建草稿，不会自动发布。</small>
            <div>
              <AimaButton
                size="small"
                @click="schemeCopyName = ''"
              >
                取消
              </AimaButton><AimaButton
                variant="primary"
                size="small"
                :disabled="saving || !schemeCopyName.trim()"
                @click="copySelectedScheme"
              >
                创建副本
              </AimaButton>
            </div>
          </div>
          <label>
            规则名称
            <input
              v-model="schemeDraft.schemeName"
              :readonly="selectedSchemeVersion?.version.status === 'draft'"
            >
            <small v-if="selectedSchemeVersion?.version.status === 'draft'">编辑现有草稿时名称保持不变；需要新名称时，请基于已发布或历史版本新建草稿。</small>
          </label>
          <label>
            说明
            <input v-model="schemeDraft.description">
          </label>
          <label>
            发声类型（每行一个）
            <textarea
              v-model="schemeDraft.voiceTypes"
              rows="4"
            />
          </label>
          <label>
            情感（每行一个）
            <textarea
              v-model="schemeDraft.sentiments"
              rows="4"
            />
          </label>
          <AnalysisLabelsEditor
            v-model="schemeDraft.labelsJson"
            @validity="schemeLabelsValid = $event"
          />
          <details class="advanced-editor">
            <summary>高级规则编辑</summary>
            <p>这里只维护提示词与查看机器结构；业务标签请在上方结构化编辑器修改。</p>
            <div class="advanced-editor__fields">
              <div class="technical-note taxonomy-preview">
                <strong>标签结构预览（只读）</strong>
                <pre>{{ schemeDraft.labelsJson }}</pre>
              </div>
              <label>
                提示词模板
                <textarea
                  v-model="schemeDraft.promptTemplate"
                  rows="14"
                  spellcheck="false"
                />
              </label>
              <div class="technical-note">
                提示词必须包含标签规则占位符 <code v-pre>{{AIMA_TAXONOMY_JSON}}</code>，发布时由后端再次校验。
              </div>
            </div>
          </details>
          <div class="actions">
            <AimaButton
              :disabled="saving || !schemeLabelsValid"
              @click="saveSchemeDraft"
            >
              {{ selectedSchemeVersion?.version.status === 'draft' ? '保存草稿' : '基于此版本新建草稿' }}
            </AimaButton>
            <AimaButton
              v-if="selectedSchemeVersion?.version.status === 'draft'"
              variant="primary"
              @click="publishVersion(selectedSchemeVersion.version)"
            >
              发布
            </AimaButton>
            <AimaButton
              v-else-if="selectedSchemeVersion && selectedSchemeVersion.scheme.active_version_id !== selectedSchemeVersion.version.id"
              @click="rollbackVersion(selectedSchemeVersion.version)"
            >
              恢复到此版本
            </AimaButton>
          </div>
        </section>
      </div>

      <ProviderConfigurationPanel
        v-else-if="tab === 'llm'"
        provider-kind="llm"
      />
      <ProviderConfigurationPanel
        v-else-if="tab === 'tikhub'"
        provider-kind="collection"
      />

      <section
        v-else
        class="card audit-card"
      >
        <header>
          <div>
            <h2>操作记录</h2>
            <p>默认只展示“谁在什么时候做了什么、影响了什么”。系统仍保留可追溯的技术信息，但不会把原始字段和 JSON 直接暴露在主视图。共 {{ auditTotal }} 条。</p>
          </div>
          <AimaButton
            size="small"
            :disabled="auditLoading"
            @click="loadAudit"
          >
            刷新
          </AimaButton>
        </header>
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>操作人</th>
              <th>操作</th>
              <th>影响对象</th>
              <th>操作说明</th>
              <th>详情</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="event in auditEvents"
              :key="event.id"
            >
              <td>{{ formatDateTime(event.created_at) }}</td>
              <td>{{ auditActorLabel(event.actor_ref) }}</td>
              <td>
                <strong>{{ auditActionLabel(event.event_type) }}</strong>
              </td>
              <td>{{ auditObjectLabel(event.object_type, event.object_id) }}</td>
              <td>{{ auditSummaryText(event) }}</td>
              <td>
                <details class="technical-details audit-details">
                  <summary>技术详情</summary>
                  <dl>
                    <div>
                      <dt>事件类型</dt>
                      <dd>{{ event.event_type }}</dd>
                    </div>
                    <div>
                      <dt>对象类型</dt>
                      <dd>{{ event.object_type ?? '—' }}</dd>
                    </div>
                    <div>
                      <dt>对象标识</dt>
                      <dd>{{ event.object_id ?? '—' }}</dd>
                    </div>
                    <div>
                      <dt>请求标识</dt>
                      <dd>{{ event.request_id ?? '—' }}</dd>
                    </div>
                  </dl>
                  <div class="raw-detail">
                    <strong>安全审计数据</strong>
                    <pre>{{ safeJson(event.safe_detail) }}</pre>
                  </div>
                </details>
              </td>
            </tr>
          </tbody>
        </table>
        <nav
          v-if="auditTotal > 0"
          class="audit-pagination"
          aria-label="操作记录分页"
        >
          <span>第 {{ Math.floor(auditOffset / auditLimit) + 1 }} / {{ Math.ceil(auditTotal / auditLimit) }} 页 · 共 {{ auditTotal }} 条</span>
          <div>
            <AimaButton
              size="small"
              :disabled="auditLoading || auditOffset === 0"
              @click="previousAuditPage"
            >
              上一页
            </AimaButton>
            <AimaButton
              size="small"
              :disabled="auditLoading || auditOffset + auditLimit >= auditTotal"
              @click="nextAuditPage"
            >
              下一页
            </AimaButton>
          </div>
        </nav>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.admin-page { display: grid; gap: 12px; }
.tabs { display: flex; min-height: 44px; align-items: end; gap: 4px; border-bottom: 1px solid var(--aima-border); }
.tabs button { height: 42px; padding: 0 18px; border: 0; border-bottom: 2px solid transparent; color: var(--aima-text-muted); background: transparent; cursor: pointer; }
.tabs button.active { border-color: var(--aima-primary); color: var(--aima-primary); font-weight: 600; }
.state-card,
.card { min-width: 0; padding: 16px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); background: var(--aima-surface); }
.state-card { color: var(--aima-text-muted); text-align: center; }
.two-column { display: grid; grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr); gap: 12px; }
.scheme-layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 12px; }
.card > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
h2, h3, p { margin: 0; }
h2 { color: var(--aima-text); font-size: 15px; }
h3 { color: var(--aima-text-secondary); font-size: 12px; }
.card p { margin-top: 4px; color: var(--aima-text-muted); font-size: 11px; line-height: 17px; }
table { width: 100%; border-collapse: collapse; font-size: 11px; }
th, td { padding: 10px 8px; border-bottom: 1px solid var(--aima-border); color: var(--aima-text-secondary); text-align: left; vertical-align: top; }
th { color: var(--aima-text-muted); background: #f8f9fb; font-weight: 500; }
td strong, td small { display: block; }
td small { margin-top: 3px; color: var(--aima-text-disabled); }
td button { margin-right: 8px; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 11px; }
td button:disabled { color: var(--aima-text-disabled); cursor: not-allowed; }
.status { padding: 2px 6px; border-radius: 4px; color: #12804b; background: #e8fff3; }
.status--deprecated, .status--merged { color: var(--aima-text-muted); background: #f2f4f7; }
.form-card { display: grid; align-content: start; gap: 12px; }
.form-card label { display: grid; gap: 6px; color: var(--aima-text-muted); font-size: 11px; }
.form-card label > small { color: var(--aima-text-disabled); font-size: 10px; line-height: 15px; }
input:read-only, input:disabled { cursor: not-allowed; color: var(--aima-text-muted); background: #f5f7fa; }
input, textarea, select { width: 100%; box-sizing: border-box; padding: 8px 10px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-control); outline: none; color: var(--aima-text-secondary); background: var(--aima-surface); font: inherit; font-size: 12px; }
input, select { height: 38px; }
textarea { resize: vertical; line-height: 18px; }
input:focus, textarea:focus, select:focus { border-color: var(--aima-primary); box-shadow: 0 0 0 2px var(--aima-primary-soft); }
.actions { display: flex; justify-content: flex-end; gap: 8px; }
hr { width: 100%; margin: 4px 0; border: 0; border-top: 1px solid var(--aima-border); }
.list-card { display: grid; align-content: start; gap: 8px; }
.list-card > button { display: grid; gap: 4px; padding: 10px 12px; border: 1px solid var(--aima-border); border-radius: 7px; color: var(--aima-text-secondary); background: var(--aima-surface); cursor: pointer; text-align: left; }
.list-card > button.active { border-color: var(--aima-primary); background: var(--aima-primary-soft); }
.list-card > button strong { font-size: 12px; }
.list-card > button span { color: var(--aima-text-muted); font-size: 10px; }
.scheme-editor > header > span { padding: 3px 8px; border-radius: 4px; color: var(--aima-primary); background: var(--aima-primary-soft); font-size: 10px; }
.scheme-resource-actions { display: flex; justify-content: flex-end; gap: 8px; }
.scheme-copy-editor { display: grid; gap: 8px; padding: 10px; border: 1px solid var(--aima-border); border-radius: 7px; background: #fafbfc; }.scheme-copy-editor small { color: var(--aima-text-muted); font-size: 10px; }.scheme-copy-editor > div { display: flex; justify-content: flex-end; gap: 8px; }
.archived-schemes { margin-top: 10px; border: 1px solid var(--aima-border); border-radius: 7px; overflow: hidden; }.archived-schemes summary { padding: 9px 10px; cursor: pointer; color: var(--aima-text-secondary); font-size: 11px; font-weight: 600; }.archived-scheme-state { padding: 12px 10px; color: var(--aima-text-muted); font-size: 10px; }.archived-scheme-row { display: grid; grid-template-columns: minmax(0,1fr) auto auto; align-items: center; gap: 5px; padding: 8px 9px; border-top: 1px solid var(--aima-border); }.archived-scheme-row span strong,.archived-scheme-row span small { display: block; }.archived-scheme-row span strong { color: var(--aima-text); font-size: 10px; }.archived-scheme-row span small { margin-top: 2px; color: var(--aima-text-disabled); font-size: 9px; }
.taxonomy-preview pre { max-height: 180px; overflow: auto; margin: 6px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--aima-text-secondary); font-size: 10px; line-height: 15px; }
.retry-link { width: max-content; padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 11px; }
.retry-link:disabled { cursor: wait; opacity: .6; }
.advanced-editor,
.technical-details { border: 1px solid var(--aima-border); border-radius: 7px; background: #fafbfc; }
.advanced-editor > summary,
.technical-details > summary { padding: 9px 10px; color: var(--aima-primary); cursor: pointer; font-size: 10px; font-weight: 600; }
.advanced-editor > p { margin: 0; padding: 0 10px 10px; }
.advanced-editor__fields { display: grid; gap: 12px; padding: 0 10px 10px; }
.technical-note { padding: 9px 10px; border-radius: 5px; color: var(--aima-text-muted); background: var(--aima-surface); font-size: 10px; line-height: 16px; }
.technical-note code { color: var(--aima-primary); }
.audit-card { overflow: auto; }
.audit-card table { min-width: 940px; }
.audit-details { min-width: 120px; }
.audit-details dl { display: grid; gap: 6px; margin: 0; padding: 0 10px 10px; }
.audit-details dl > div { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 8px; }
.audit-details dt { color: var(--aima-text-muted); font-size: 9px; }
.audit-details dd { min-width: 0; margin: 0; overflow-wrap: anywhere; color: var(--aima-text-secondary); font-size: 9px; }
.raw-detail { display: grid; gap: 5px; padding: 0 10px 10px; }
.raw-detail > strong { color: var(--aima-text-muted); font-size: 9px; }
.raw-detail pre { max-width: 420px; max-height: 220px; margin: 0; overflow: auto; padding: 8px; border-radius: 5px; color: var(--aima-text-secondary); background: var(--aima-surface); white-space: pre-wrap; overflow-wrap: anywhere; font-size: 9px; line-height: 14px; }
.audit-pagination { display: flex; min-height: 48px; align-items: center; justify-content: space-between; gap: 16px; padding-top: 10px; color: var(--aima-text-muted); font-size: 11px; }
.audit-pagination > div { display: flex; gap: 8px; }
@media (max-width: 1280px) { .two-column, .scheme-layout { grid-template-columns: 1fr; } }
</style>
