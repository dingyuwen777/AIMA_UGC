<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import type {
  AnalysisSchemeDefinitionRequest,
  AnalysisSchemeResponse,
  AnalysisSchemeVersionResponse,
  ResourceLifecycleResponse,
} from '../../../../../generated/api/client'
import { apiErrorMessage } from '../../../../../shared/api/http'
import { formatDateTime } from '../../../../../shared/domain/beijingTime'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import {
  activateScheme,
  addSchemeDraft,
  archiveScheme,
  copyScheme,
  deleteArchivedScheme,
  editSchemeDraft,
  fetchArchivedSchemes,
  fetchSchemeDeleteEligibility,
  fetchSchemes,
  restoreArchivedScheme,
  restoreScheme,
} from '../../../api'
import AnalysisLabelsEditor from '../../../components/AnalysisLabelsEditor.vue'
import { formatRuntimeStatus } from '../../../presentation'

const saving = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)
const schemes = ref<AnalysisSchemeResponse[]>([])
const archivedSchemes = ref<ResourceLifecycleResponse[]>([])
const selectedSchemeVersionId = ref('')
const archivedSchemeLoading = ref(false)
const schemeLabelsValid = ref(true)
const schemeCopyName = ref('')
const schemeCopyEditing = ref(false)

const schemeDraft = reactive({
  schemeName: '',
  description: '',
  promptTemplate: '',
  voiceTypes: '',
  sentiments: '',
  labelsJson: '{}',
})

const selectedSchemeVersion = computed(() => {
  for (const scheme of schemes.value) {
    const version = scheme.versions.find((item) => item.id === selectedSchemeVersionId.value)
    if (version) return { scheme, version }
  }
  return null
})

/** 发布只能消费已持久化草稿，未保存编辑不能直接生效。 */
const hasUnsavedSchemeChanges = computed(() => {
  const selected = selectedSchemeVersion.value
  if (!selected || selected.version.status !== 'draft') return false
  if (!schemeLabelsValid.value) return true
  try {
    const definition = schemeDefinition()
    const saved = selected.version.definition
    return schemeDraft.description !== selected.version.description
      || definition.prompt_template !== saved.prompt_template
      || JSON.stringify(definition.voice_types) !== JSON.stringify(saved.voice_types)
      || JSON.stringify(definition.sentiments) !== JSON.stringify(saved.sentiments)
      || JSON.stringify(definition.labels) !== JSON.stringify(saved.labels)
  } catch {
    return true
  }
})

onMounted(loadSchemes)

/** 读取全部分析规则并默认定位当前生效版本。 */
async function loadSchemes(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    schemes.value = (await fetchSchemes()).items
    const knownVersion = schemes.value
      .flatMap((item) => item.versions)
      .some((item) => item.id === selectedSchemeVersionId.value)
    if (!knownVersion) {
      const activeVersionIds = new Set(
        schemes.value.flatMap((item) => item.active_version_id ? [item.active_version_id] : []),
      )
      const initial = schemes.value.flatMap((item) => item.versions)
        .find((item) => activeVersionIds.has(item.id))
        ?? schemes.value.flatMap((item) => item.versions)[0]
      selectedSchemeVersionId.value = initial?.id ?? ''
      if (initial) selectSchemeVersion(initial.id)
    } else if (selectedSchemeVersion.value) {
      syncSchemeDraft(selectedSchemeVersion.value.scheme, selectedSchemeVersion.value.version)
    }
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    loading.value = false
  }
}

/** 已归档规则只在用户展开时读取。 */
async function loadArchivedSchemes(): Promise<void> {
  archivedSchemeLoading.value = true
  error.value = null
  try {
    archivedSchemes.value = (await fetchArchivedSchemes()).items
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    archivedSchemeLoading.value = false
  }
}

/** 展开归档列表时触发一次读取。 */
function onArchivedSchemesToggle(event: Event): void {
  if ((event.currentTarget as HTMLDetailsElement).open) void loadArchivedSchemes()
}

/** 将多行或逗号输入规范为去重的非空项。 */
function splitLines(value: string): string[] {
  return [...new Set(value.split(/[\n,，]/).map((item) => item.trim()).filter(Boolean))]
}

/** 切换版本时重建编辑基线。 */
function selectSchemeVersion(versionId: string): void {
  schemeCopyEditing.value = false
  schemeCopyName.value = ''
  selectedSchemeVersionId.value = versionId
  const selection = schemes.value
    .flatMap((scheme) => scheme.versions.map((version) => ({ scheme, version })))
    .find((item) => item.version.id === versionId)
  if (selection) syncSchemeDraft(selection.scheme, selection.version)
}

/** 版本状态转换为管理员业务语言。 */
function schemeVersionStateLabel(
  scheme: AnalysisSchemeResponse,
  version: AnalysisSchemeVersionResponse,
): string {
  if (scheme.active_version_id === version.id) return '当前生效'
  if (version.status === 'draft') return '草稿，尚未生效'
  return formatRuntimeStatus(version.status)
}

/** 以服务端版本作为编辑基线。 */
function syncSchemeDraft(
  scheme: AnalysisSchemeResponse,
  version: AnalysisSchemeResponse['versions'][number],
): void {
  Object.assign(schemeDraft, {
    schemeName: scheme.name,
    description: version.description,
    promptTemplate: version.definition.prompt_template,
    voiceTypes: version.definition.voice_types.join('\n'),
    sentiments: version.definition.sentiments.join('\n'),
    labelsJson: JSON.stringify(version.definition.labels, null, 2),
  })
}

/** 结构化页面输入转换成正式 Scheme Definition。 */
function schemeDefinition(): AnalysisSchemeDefinitionRequest {
  return {
    prompt_template: schemeDraft.promptTemplate,
    voice_types: splitLines(schemeDraft.voiceTypes),
    sentiments: splitLines(schemeDraft.sentiments),
    labels: JSON.parse(schemeDraft.labelsJson) as Record<string, string[]>,
  }
}

/** 前端只执行与后端一致的最小发布资格预检。 */
function validateSchemeDefinition(definition: AnalysisSchemeDefinitionRequest): void {
  if (!schemeLabelsValid.value) throw new Error('请先修正结构化标签规则。')
  if (!definition.prompt_template.includes('{{AIMA_TAXONOMY_JSON}}')) {
    throw new Error('提示词模板必须包含标签规则占位符 {{AIMA_TAXONOMY_JSON}}。')
  }
  if (!definition.voice_types.length || !definition.sentiments.length || !Object.keys(definition.labels).length) {
    throw new Error('发声类型、情感和标签都不能为空。')
  }
}

/** 保存草稿后始终使用服务端返回版本更新页面。 */
async function saveSchemeDraft(): Promise<void> {
  saving.value = true
  error.value = null
  notice.value = null
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
    const draft = saved.versions.find((item) => item.status === 'draft')
    selectedSchemeVersionId.value = draft?.id ?? ''
    if (draft) syncSchemeDraft(saved, draft)
    notice.value = 'AI 分析规则草稿已保存并记录操作。'
    await loadSchemes()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

/** 打开复制规则的名称编辑器。 */
function startSchemeCopy(): void {
  const selected = selectedSchemeVersion.value
  if (!selected) return
  schemeCopyEditing.value = true
  schemeCopyName.value = `${selected.scheme.name} 副本`
}

/** 复制当前规则到新草稿。 */
async function copySelectedScheme(): Promise<void> {
  const selected = selectedSchemeVersion.value
  if (!selected || !schemeCopyName.value.trim()) return
  saving.value = true
  error.value = null
  notice.value = null
  try {
    const copied = await copyScheme(selected.scheme.id, { name: schemeCopyName.value.trim() })
    schemeCopyEditing.value = false
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

/** 归档当前规则；当前生效规则的最终限制由服务端守卫。 */
async function archiveSelectedScheme(): Promise<void> {
  const selected = selectedSchemeVersion.value
  if (!selected || saving.value) return
  if (!window.confirm(`确认归档 AI 分析规则“${selected.scheme.name}”吗？当前生效规则会被服务端阻止归档，历史版本和历史分析任务不会被删除。`)) return
  saving.value = true
  error.value = null
  notice.value = null
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

/** 恢复归档规则但不自动发布。 */
async function restoreArchivedAnalysisScheme(item: ResourceLifecycleResponse): Promise<void> {
  saving.value = true
  error.value = null
  notice.value = null
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

/** 永久删除前先读取后端资格，历史规则不能被页面强行删除。 */
async function deleteArchivedAnalysisScheme(item: ResourceLifecycleResponse): Promise<void> {
  saving.value = true
  error.value = null
  notice.value = null
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

/** 发布已保存草稿；页面存在未保存输入时禁止发出请求。 */
async function publishVersion(version: AnalysisSchemeVersionResponse): Promise<void> {
  if (saving.value || hasUnsavedSchemeChanges.value) return
  if (!window.confirm('发布后，新建的 AI 分析任务会使用此版本；正在运行的任务不受影响。是否发布？')) return
  saving.value = true
  error.value = null
  notice.value = null
  try {
    await activateScheme(version.id, version.version)
    notice.value = 'AI 分析规则已发布并记录操作。'
    await loadSchemes()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

/** 恢复历史版本，完整版本冲突与审计仍由服务端处理。 */
async function rollbackVersion(version: AnalysisSchemeVersionResponse): Promise<void> {
  if (saving.value) return
  if (!window.confirm(`确认恢复到版本 ${version.version}？系统会完整记录本次操作。`)) return
  saving.value = true
  error.value = null
  notice.value = null
  try {
    await restoreScheme(version.id, version.version)
    notice.value = `已恢复到版本 ${version.version} 并记录操作。`
    await loadSchemes()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <fieldset
    class="analysis-panel"
    :disabled="saving"
    aria-label="AI 分析规则"
  >
    <AimaFeedbackBanner
      v-if="error"
      tone="error"
      role="alert"
    >
      <strong>AI 分析规则操作失败</strong>
      <span>{{ error }}</span>
    </AimaFeedbackBanner>
    <AimaFeedbackBanner
      v-if="notice"
      tone="success"
    >
      {{ notice }}
    </AimaFeedbackBanner>

    <div
      v-if="loading"
      class="state-card"
    >
      正在加载 AI 分析规则…
    </div>

    <div
      v-else
      class="scheme-layout"
    >
      <section class="card scheme-history">
        <h2>版本历史</h2>
        <template
          v-for="scheme in schemes"
          :key="scheme.id"
        >
          <button
            v-for="version in scheme.versions"
            :key="version.id"
            type="button"
            :class="{ active: selectedSchemeVersionId === version.id }"
            @click="selectSchemeVersion(version.id)"
          >
            <strong>版本 {{ version.version }} · {{ schemeVersionStateLabel(scheme, version) }}</strong>
            <span>{{ formatDateTime(version.created_at) }}</span>
          </button>
        </template>

        <div class="publish-policy">
          <strong>发布策略</strong>
          <span>保存草稿不会影响当前任务。</span>
          <span>发布后仅新任务使用新版本。</span>
          <span>历史版本可随时恢复。</span>
        </div>

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
            <span>
              <strong>{{ item.name }}</strong>
              <small>{{ formatDateTime(item.archived_at) }}</small>
            </span>
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

      <section class="card scheme-editor">
        <header>
          <div>
            <h2>
              AI 分析规则
              <template v-if="selectedSchemeVersion">
                · {{ schemeVersionStateLabel(selectedSchemeVersion.scheme, selectedSchemeVersion.version) }}
              </template>
            </h2>
            <p>按业务含义维护发声类型、情感和标签；修改后先生成草稿。</p>
          </div>
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
        </header>

        <div
          v-if="schemeCopyEditing"
          class="scheme-copy-editor"
        >
          <label>
            副本名称
            <input
              v-model="schemeCopyName"
              maxlength="200"
            >
          </label>
          <small>复制的是该规则当前最新版本；副本只创建草稿，不会自动发布。</small>
          <div>
            <AimaButton
              size="small"
              @click="schemeCopyEditing = false"
            >
              取消
            </AimaButton>
            <AimaButton
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
          发声类型
          <textarea
            v-model="schemeDraft.voiceTypes"
            rows="4"
          />
        </label>
        <label>
          情感
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

        <p
          v-if="hasUnsavedSchemeChanges"
          class="unsaved-hint"
        >
          规则有未保存修改，请先保存草稿后再发布。
        </p>

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
            :disabled="saving || hasUnsavedSchemeChanges"
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
  </fieldset>
</template>

<style scoped>
.analysis-panel { display: grid; margin: 0; padding: 0; border: 0; gap: 16px; min-width: 0; }
.state-card,
.card { min-width: 0; padding: 16px; border: 1px solid var(--aima-border); border-radius: 8px; background: var(--aima-surface); }
.state-card { color: var(--aima-text-muted); text-align: center; }
.scheme-layout { display: grid; grid-template-columns: 268px minmax(760px, 1fr); align-items: start; gap: 24px; min-width: 0; }
.scheme-history,
.scheme-editor { height: min(664px, calc(100dvh - 184px)); overflow-y: auto; }
.scheme-history { display: grid; align-content: start; gap: 10px; }
h2, p { margin: 0; }
h2 { color: var(--aima-text); font-size: 16px; font-weight: 500; line-height: 24px; }
.scheme-history > button { display: grid; gap: 5px; padding: 10px 12px; border: 1px solid var(--aima-border); border-radius: 6px; color: var(--aima-text-secondary); background: var(--aima-surface); cursor: pointer; text-align: left; }
.scheme-history > button.active { border-color: var(--aima-primary); color: var(--aima-primary); background: var(--aima-primary-soft); }
.scheme-history > button strong { font-size: 12px; }
.scheme-history > button span { color: var(--aima-text-disabled); font-size: 9px; }
.publish-policy { display: grid; gap: 4px; margin-top: 8px; color: var(--aima-text-disabled); font-size: 10px; line-height: 16px; }
.publish-policy strong { margin-bottom: 4px; color: var(--aima-text); font-size: 12px; }
.archived-schemes { margin-top: 8px; border-top: 1px solid var(--aima-border); padding-top: 10px; }
.archived-schemes summary { cursor: pointer; color: var(--aima-text-secondary); font-size: 11px; font-weight: 600; }
.archived-scheme-state { padding: 10px 0; color: var(--aima-text-muted); font-size: 10px; }
.archived-scheme-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 6px; padding: 8px 0; border-top: 1px solid var(--aima-border); }
.archived-scheme-row strong,
.archived-scheme-row small { display: block; }
.archived-scheme-row strong { font-size: 11px; }
.archived-scheme-row small { color: var(--aima-text-disabled); font-size: 9px; }
.scheme-editor { display: grid; align-content: start; gap: 12px; }
.scheme-editor > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.scheme-editor > header p { margin-top: 4px; color: var(--aima-text-muted); font-size: 11px; line-height: 16px; }
.scheme-resource-actions { display: flex; gap: 8px; }
.scheme-editor > label,
.scheme-copy-editor label,
.advanced-editor label { display: grid; gap: 6px; color: var(--aima-text-tertiary, #a8b0bf); font-size: 11px; line-height: 16px; }
.scheme-editor label > small { color: var(--aima-text-disabled); font-size: 10px; line-height: 15px; }
input, textarea { width: 100%; box-sizing: border-box; padding: 8px 12px; border: 1px solid var(--aima-border-strong); border-radius: 8px; outline: none; color: var(--aima-text); background: var(--aima-surface); font: inherit; font-size: 13px; line-height: 20px; }
input { height: 40px; }
textarea { min-height: 88px; resize: vertical; }
input:focus, textarea:focus { border-color: var(--aima-primary); box-shadow: 0 0 0 2px var(--aima-primary-soft); }
input:read-only { color: var(--aima-text-disabled); background: var(--aima-color-bg-disabled, #f2f5f7); }
.scheme-copy-editor { display: grid; gap: 8px; padding: 12px; border: 1px solid var(--aima-border); border-radius: 8px; background: #fbfcfe; }
.scheme-copy-editor small { color: var(--aima-text-disabled); font-size: 10px; }
.scheme-copy-editor > div { display: flex; justify-content: flex-end; gap: 8px; }
.advanced-editor { border: 1px solid var(--aima-border); border-radius: 8px; padding: 10px 12px; }
.advanced-editor summary { cursor: pointer; color: var(--aima-text-secondary); font-size: 12px; font-weight: 500; }
.advanced-editor > p { margin: 8px 0; color: var(--aima-text-muted); font-size: 11px; }
.advanced-editor__fields { display: grid; gap: 10px; }
.technical-note { padding: 10px 12px; border-radius: 7px; color: var(--aima-text-muted); background: #f6f8fb; font-size: 10px; line-height: 16px; }
.taxonomy-preview pre { max-height: 220px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
.unsaved-hint { color: var(--aima-color-warning, #d48806); font-size: 11px; }
.actions { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; padding-top: 4px; }

.analysis-panel :deep(.labels-editor) { gap: 12px; padding: 0; border: 0; background: transparent; }
.analysis-panel :deep(.labels-editor > header) { display: none; }
.analysis-panel :deep(.label-groups) { gap: 12px; }
.analysis-panel :deep(.label-group) { gap: 8px; padding: 12px; border: 0; border-radius: 0; background: #fff; }
.analysis-panel :deep(.label-group input) { height: 40px; padding: 0 12px; border-radius: 8px; font-size: 13px; }
.analysis-panel :deep(.primary-row) { grid-template-columns: minmax(0, 1fr); }
.analysis-panel :deep(.secondary-list) { grid-template-columns: 1fr; }
.analysis-panel :deep(.label-group label) { gap: 6px; font-size: 11px; }
.analysis-panel :deep(.labels-editor > .aima-button) { justify-self: start; }

@media (max-width: 1439px) {
  .scheme-layout { grid-template-columns: 1fr; }
  .scheme-history,
  .scheme-editor { width: 100%; height: auto; min-height: 0; max-height: none; }
}
</style>
