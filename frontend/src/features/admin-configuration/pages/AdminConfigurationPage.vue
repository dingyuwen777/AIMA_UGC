<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import type {
  AnalysisSchemeDefinitionRequest,
  AnalysisSchemeResponse,
  AnalysisSchemeVersionResponse,
  AuditEventResponse,
  KeywordPackSummaryResponse,
  VehicleModelResponse,
} from '../../../generated/api/client'
import AppShell from '../../../app/layouts/AppShell.vue'
import { apiErrorMessage } from '../../../shared/api/http'
import AimaButton from '../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../shared/ui/AimaFeedbackBanner.vue'
import AimaPageHeader from '../../../shared/ui/AimaPageHeader.vue'
import VehicleMultiSelect from '../../../shared/VehicleMultiSelect.vue'
import { formatDateTime } from '../../../shared/domain/beijingTime'
import {
  activateScheme,
  addSchemeDraft,
  addVehicle,
  editSchemeDraft,
  editVehicle,
  fetchAuditEvents,
  fetchKeywordPacksForAdmin,
  fetchSchemes,
  fetchVehicles,
  mergeVehicle,
  removeVehicle,
  restoreScheme,
  saveKeywordPackVehicles,
} from '../api'

type Tab = 'vehicles' | 'links' | 'scheme' | 'audit'

const tab = ref<Tab>('vehicles')
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)
const vehicles = ref<VehicleModelResponse[]>([])
const packs = ref<KeywordPackSummaryResponse[]>([])
const schemes = ref<AnalysisSchemeResponse[]>([])
const auditEvents = ref<AuditEventResponse[]>([])
const selectedPackId = ref('')
const linkedVehicleIds = ref<string[]>([])
const selectedSchemeVersionId = ref('')

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

const selectedPack = computed(() => packs.value.find((item) => item.id === selectedPackId.value) ?? null)
const selectedSchemeVersion = computed(() => {
  for (const scheme of schemes.value) {
    const version = scheme.versions.find((item) => item.id === selectedSchemeVersionId.value)
    if (version) return { scheme, version }
  }
  return null
})

onMounted(refreshAll)

async function refreshAll(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [vehicleResponse, packResponse, schemeResponse, auditResponse] = await Promise.all([
      fetchVehicles(),
      fetchKeywordPacksForAdmin(),
      fetchSchemes(),
      fetchAuditEvents(),
    ])
    vehicles.value = vehicleResponse.items
    packs.value = packResponse.items
    schemes.value = schemeResponse.items
    auditEvents.value = auditResponse.items
    if (!selectedPackId.value && packs.value[0]) selectPack(packs.value[0].id)
    if (!selectedSchemeVersionId.value) {
      const initial = schemes.value.flatMap((item) => item.versions).find((item) => item.status === 'draft')
        ?? schemes.value.flatMap((item) => item.versions)[0]
      if (initial) selectSchemeVersion(initial.id)
    }
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    loading.value = false
  }
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
    notice.value = vehicleDraft.id ? '车型已更新并写入审计。' : '车型已创建并写入审计。'
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
    error.value = '该车型已被业务数据引用，不能物理删除；请停用、改名或合并。'
    return
  }
  if (!window.confirm(`确定删除未引用车型“${item.display_name}”吗？此操作会写入审计。`)) return
  try {
    await removeVehicle(item.id)
    notice.value = '未引用车型已删除并写入审计。'
    await refreshAll()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  }
}

async function mergeSelectedVehicle(): Promise<void> {
  if (!vehicleDraft.id || !mergeTargetId.value) return
  if (!window.confirm('合并会保留历史证据并把后续选择重定向到目标车型，是否继续？')) return
  try {
    await mergeVehicle(vehicleDraft.id, { target_vehicle_model_id: mergeTargetId.value })
    notice.value = '车型已合并并写入审计。'
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
    notice.value = '词包与车型关联已更新并写入审计。'
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
  if (!definition.prompt_template.includes('{{AIMA_TAXONOMY_JSON}}')) {
    throw new Error('Prompt 模板必须且只能通过 {{AIMA_TAXONOMY_JSON}} 注入当前 Taxonomy。')
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
        name: schemeDraft.schemeName || `${selected?.scheme.name ?? 'Analysis Scheme'} 草稿`,
        description: schemeDraft.description,
        definition,
      })
    }
    selectedSchemeVersionId.value = saved.versions.find((item) => item.status === 'draft')?.id ?? ''
    notice.value = 'Analysis Scheme 草稿已保存并写入审计。'
    await refreshAll()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

async function publishVersion(version: AnalysisSchemeVersionResponse): Promise<void> {
  if (!window.confirm('发布后，新 Analysis Run 将冻结使用此版本；当前运行中的任务不受影响。是否发布？')) return
  try {
    await activateScheme(version.id, version.version)
    notice.value = 'Analysis Scheme 已发布并写入审计。'
    await refreshAll()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  }
}

async function rollbackVersion(version: AnalysisSchemeVersionResponse): Promise<void> {
  if (!window.confirm(`确认回滚到版本 v${version.version}？该操作无需双人审批，但会完整审计。`)) return
  try {
    await restoreScheme(version.id, version.version)
    notice.value = `已回滚到 v${version.version} 并写入审计。`
    await refreshAll()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  }
}
</script>

<template>
  <AppShell section-title="管理员配置">
    <div class="admin-page">
      <AimaPageHeader
        title="管理员配置"
        description="车型、词包关联与 Analysis Scheme 的唯一管理入口；所有修改、发布和回滚均写入审计。"
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
          v-for="item in ([['vehicles', '车型目录'], ['links', '词包车型关联'], ['scheme', 'Analysis Scheme'], ['audit', '审计记录']] as const)"
          :key="item[0]"
          type="button"
          :class="{ active: tab === item[0] }"
          @click="tab = item[0]"
        >
          {{ item[1] }}
        </button>
      </nav>

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
            <div><h2>车型目录</h2><p>稳定 code 不改写；有引用的车型仅允许停用、改名或合并。</p></div><AimaButton
              size="small"
              @click="resetVehicleDraft"
            >
              新增车型
            </AimaButton>
          </header>
          <table>
            <thead><tr><th>车型</th><th>别名</th><th>状态</th><th>引用</th><th>操作</th></tr></thead>
            <tbody>
              <tr
                v-for="item in vehicles"
                :key="item.id"
              >
                <td><strong>{{ item.display_name }}</strong><small>{{ item.code }} · v{{ item.version }}</small></td><td>{{ (item.aliases ?? []).map((alias) => alias.text).join('、') || '—' }}</td><td>
                  <span
                    class="status"
                    :class="`status--${item.status}`"
                  >{{ item.status }}</span>
                </td><td>{{ item.referenced ? '已引用' : '未引用' }}</td><td>
                  <button
                    type="button"
                    @click="editVehicleDraft(item)"
                  >
                    编辑
                  </button><button
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
          <label>稳定 code<input
            v-model="vehicleDraft.code"
            :disabled="Boolean(vehicleDraft.id)"
            placeholder="例如 AIMA-Q7"
          ></label>
          <label>显示名称<input
            v-model="vehicleDraft.displayName"
            placeholder="例如 爱玛 Q7"
          ></label>
          <label>别名（每行一个）<textarea
            v-model="vehicleDraft.aliases"
            rows="6"
            placeholder="Q7&#10;爱玛Q7"
          /></label>
          <label v-if="vehicleDraft.id">状态<select v-model="vehicleDraft.status"><option value="active">active</option><option value="deprecated">deprecated</option></select></label>
          <div class="actions">
            <AimaButton @click="resetVehicleDraft">
              取消
            </AimaButton><AimaButton
              variant="primary"
              :disabled="saving"
              @click="saveVehicle"
            >
              保存
            </AimaButton>
          </div>
          <template v-if="vehicleDraft.id">
            <hr><h3>合并重复车型</h3><select v-model="mergeTargetId">
              <option value="">
                选择目标车型
              </option><option
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
          <h2>选择词包</h2><button
            v-for="pack in packs"
            :key="pack.id"
            type="button"
            :class="{ active: selectedPackId === pack.id }"
            @click="selectPack(pack.id)"
          >
            <strong>{{ pack.name }}</strong><span>v{{ pack.version }} · {{ pack.enabled ? '启用' : '停用' }}</span>
          </button>
        </section>
        <section class="card form-card">
          <h2>{{ selectedPack?.name ?? '词包车型关联' }}</h2><p>同一维度内车型按 OR；与词包关键词维度按 AND。保存时冻结关联版本。</p><VehicleMultiSelect
            v-model="linkedVehicleIds"
            label="关联车型（可多选）"
          /><div class="actions">
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
          <h2>版本历史</h2><template
            v-for="scheme in schemes"
            :key="scheme.id"
          >
            <h3>{{ scheme.name }}</h3><button
              v-for="version in scheme.versions"
              :key="version.id"
              type="button"
              :class="{ active: selectedSchemeVersionId === version.id }"
              @click="selectSchemeVersion(version.id)"
            >
              <strong>v{{ version.version }} · {{ version.status }}</strong><span>{{ formatDateTime(version.created_at) }}</span>
            </button>
          </template>
        </section>
        <section class="card form-card scheme-editor">
          <header><div><h2>原子 Analysis Scheme</h2><p>Prompt、发声类型、情感和标签一次发布，避免耦合配置漂移。</p></div><span v-if="selectedSchemeVersion">{{ selectedSchemeVersion.version.status }}</span></header><label>Scheme 名称<input v-model="schemeDraft.schemeName"></label><label>说明<input v-model="schemeDraft.description"></label><label>发声类型（每行一个）<textarea
            v-model="schemeDraft.voiceTypes"
            rows="4"
          /></label><label>情感（每行一个）<textarea
            v-model="schemeDraft.sentiments"
            rows="4"
          /></label><label>标签 JSON<textarea
            v-model="schemeDraft.labelsJson"
            rows="10"
            spellcheck="false"
          /></label><label>Prompt 模板<textarea
            v-model="schemeDraft.promptTemplate"
            rows="14"
            spellcheck="false"
          /></label><p class="hint">
            必须包含占位符 <code v-pre>{{AIMA_TAXONOMY_JSON}}</code>；后端发布时重新校验并计算 Hash。
          </p><div class="actions">
            <AimaButton
              :disabled="saving"
              @click="saveSchemeDraft"
            >
              {{ selectedSchemeVersion?.version.status === 'draft' ? '保存草稿' : '基于此版本新建草稿' }}
            </AimaButton><AimaButton
              v-if="selectedSchemeVersion?.version.status === 'draft'"
              variant="primary"
              @click="publishVersion(selectedSchemeVersion.version)"
            >
              发布
            </AimaButton><AimaButton
              v-else-if="selectedSchemeVersion && selectedSchemeVersion.scheme.active_version_id !== selectedSchemeVersion.version.id"
              @click="rollbackVersion(selectedSchemeVersion.version)"
            >
              回滚到此版本
            </AimaButton>
          </div>
        </section>
      </div>

      <section
        v-else
        class="card audit-card"
      >
        <header>
          <div><h2>审计记录</h2><p>发布、回滚、车型与配置修改的安全摘要；不记录 Secret 和 Prompt 正文。</p></div><AimaButton
            size="small"
            @click="refreshAll"
          >
            刷新
          </AimaButton>
        </header><table>
          <thead><tr><th>时间</th><th>操作</th><th>操作者</th><th>对象</th><th>request_id</th><th>安全摘要</th></tr></thead><tbody>
            <tr
              v-for="event in auditEvents"
              :key="event.id"
            >
              <td>{{ formatDateTime(event.created_at) }}</td><td>{{ event.event_type }}</td><td>{{ event.actor_ref ?? 'system' }}</td><td>{{ event.object_type ?? '—' }} / {{ event.object_id ?? '—' }}</td><td>{{ event.request_id ?? '—' }}</td><td><code>{{ JSON.stringify(event.safe_detail) }}</code></td>
            </tr>
          </tbody>
        </table>
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
.hint code { color: var(--aima-primary); }
.audit-card { overflow: auto; }
.audit-card code { display: block; max-width: 360px; overflow-wrap: anywhere; white-space: normal; font-size: 9px; }
@media (max-width: 1280px) { .two-column, .scheme-layout { grid-template-columns: 1fr; } }
</style>
