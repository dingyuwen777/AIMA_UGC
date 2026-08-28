<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { DataExportResponse } from '../../../../../generated/api/client'
import { exportArtifactRetention } from '../../../../../shared/artifactRetention'
import TaskProgressBar from '../../../../../shared/TaskProgressBar.vue'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import { formatDateTime, formatNumber } from '../../../format'

const props = defineProps<{
  modelValue: boolean
  selectedCount: number
  pageCount: number
  items: DataExportResponse[]
  submitting: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [open: boolean]
  submit: [scope: 'query' | 'selected' | 'page']
  refresh: []
  download: [item: DataExportResponse]
}>()
const scope = ref<'query' | 'selected' | 'page'>('selected')

watch(() => props.modelValue, (open) => {
  if (open) scope.value = props.selectedCount > 0 ? 'selected' : props.pageCount > 0 ? 'page' : 'query'
})

const canSubmit = computed(() => {
  if (scope.value === 'selected') return props.selectedCount > 0
  return props.pageCount > 0
})

const statusLabels = {
  queued: '排队中',
  running: '导出中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

/** 复用统一 Artifact 保留策略计算当前导出记录的下载有效期。 */
function retention(item: DataExportResponse) {
  return exportArtifactRetention(item.completed_at)
}

/** 只有 Job 成功且 Artifact 尚未过期时允许下载。 */
function canDownload(item: DataExportResponse): boolean {
  const current = retention(item)
  return item.job.status === 'succeeded' && current.expiresAt !== null && !current.expired
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="modal-layer"
    >
      <button
        class="backdrop"
        type="button"
        aria-label="关闭导出弹窗"
        @click="emit('update:modelValue', false)"
      />
      <section
        class="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-title"
      >
        <header>
          <div>
            <h2 id="export-title">
              导出声音记录
            </h2>
            <p>复用正式 Excel 导出链路，后台生成可下载 Artifact。</p>
          </div>
          <button
            class="close-button"
            type="button"
            aria-label="关闭"
            @click="emit('update:modelValue', false)"
          >
            <AimaIcon
              name="close"
              :size="20"
            />
          </button>
        </header>
        <div class="body">
          <div class="choice-grid">
            <label :class="{ active: scope === 'selected', disabled: selectedCount === 0 }">
              <input
                v-model="scope"
                type="radio"
                value="selected"
                :disabled="selectedCount === 0"
              >
              <span><strong>已选内容</strong><small>{{ selectedCount }} 条</small></span>
            </label>
            <label :class="{ active: scope === 'page', disabled: pageCount === 0 }">
              <input
                v-model="scope"
                type="radio"
                value="page"
                :disabled="pageCount === 0"
              >
              <span><strong>当前页内容</strong><small>冻结已加载 {{ pageCount }} 条</small></span>
            </label>
            <label :class="{ active: scope === 'query', disabled: pageCount === 0 }">
              <input
                v-model="scope"
                type="radio"
                value="query"
                :disabled="pageCount === 0"
              >
              <span><strong>全部查询结果</strong><small>{{ pageCount > 0 ? '按当前筛选条件冻结' : '当前筛选没有可导出内容' }}</small></span>
            </label>
          </div>
          <p class="analysis-note">
            未完成 AI 打标的内容不会被丢弃：仍会导出，AI 情感和标签列留空，并在结果统计中提示。
          </p>
          <p class="retention-note">
            Excel 导出文件自生成完成后保留 7 天。过期后文件会自动清理，导出记录仍保留；需要时可重新创建导出。
          </p>
          <div class="records-title">
            <strong>最近导出记录</strong>
            <AimaButton
              variant="text"
              size="small"
              icon="refresh"
              @click="emit('refresh')"
            >
              刷新
            </AimaButton>
          </div>
          <div class="records">
            <article
              v-for="item in items"
              :key="item.id"
            >
              <div class="record-info">
                <strong>{{ item.filename || `声音广场导出 ${item.id.slice(0, 8)}` }}</strong>
                <small>{{ formatDateTime(item.created_at) }} · {{ statusLabels[item.job.status] }}</small>
                <TaskProgressBar
                  compact
                  :label="`导出 ${item.id.slice(0, 8)} 进度`"
                  :value="item.job.progress"
                  :tone="item.job.status === 'succeeded' ? 'success' : item.job.status === 'failed' ? 'danger' : 'primary'"
                />
                <span v-if="item.stats">内容 {{ formatNumber(item.stats.content_count) }} · 已打标 {{ formatNumber(item.stats.analyzed_count) }} · 未打标 {{ formatNumber(item.stats.unanalyzed_count) }}</span>
                <span
                  v-if="retention(item).expiresAt"
                  :class="{ expired: retention(item).expired }"
                >{{ retention(item).expired ? '下载已过期' : `下载有效期至 ${formatDateTime(retention(item).expiresAt)}` }}</span>
                <span
                  v-else-if="item.job.status !== 'succeeded'"
                  class="pending-artifact"
                >Artifact 尚未就绪</span>
                <span
                  v-if="item.job.error_code"
                  class="error"
                >{{ item.job.error_code }}</span>
              </div>
              <AimaButton
                size="small"
                variant="outline"
                icon="download"
                :disabled="!canDownload(item)"
                @click="emit('download', item)"
              >
                {{ retention(item).expired ? '已过期' : item.job.status === 'running' || item.job.status === 'queued' ? '导出中' : '下载' }}
              </AimaButton>
            </article>
            <p
              v-if="items.length === 0"
              class="empty"
            >
              暂无导出记录。
            </p>
          </div>
        </div>
        <footer>
          <AimaButton @click="emit('update:modelValue', false)">
            关闭
          </AimaButton>
          <AimaButton
            variant="primary"
            :disabled="submitting || !canSubmit"
            @click="emit('submit', scope)"
          >
            {{ submitting ? '正在创建…' : '创建 Excel 导出' }}
          </AimaButton>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-layer { position: fixed; z-index: 130; inset: 0; display: grid; place-items: center; }
.backdrop { position: absolute; inset: 0; border: 0; background: rgb(25 32 45 / 46%); }
.modal { position: relative; display: grid; width: min(650px, calc(100vw - 32px)); max-height: min(690px, calc(100vh - 32px)); overflow: hidden; border-radius: 11px; background: var(--aima-surface); box-shadow: 0 22px 58px rgb(20 28 42 / 22%); }
header { display: flex; min-height: 82px; align-items: center; justify-content: space-between; padding: 0 22px; border-bottom: 1px solid var(--aima-border); }
h2 { margin: 0; color: var(--aima-text); font-size: 18px; line-height: 26px; }
header p { margin: 5px 0 0; color: var(--aima-text-muted); font-size: 11px; line-height: 16px; }
.close-button { display: grid; width: 32px; height: 32px; place-items: center; border: 0; color: var(--aima-text-muted); background: transparent; cursor: pointer; }
.body { min-height: 0; padding: 18px 22px; overflow-y: auto; }
.choice-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.choice-grid label { display: flex; min-height: 82px; align-items: flex-start; gap: 8px; padding: 12px 13px; border: 1px solid var(--aima-border); border-radius: 7px; cursor: pointer; }
.choice-grid label.active { border-color: var(--aima-primary); background: var(--aima-primary-soft); }
.choice-grid label.disabled { opacity: .55; cursor: default; }
.choice-grid input { margin: 2px 0 0; accent-color: var(--aima-primary); }
.choice-grid strong,
.choice-grid small { display: block; }
.choice-grid strong { color: var(--aima-text); font-size: 11px; }
.choice-grid small { margin-top: 5px; color: var(--aima-text-muted); font-size: 9px; }
.analysis-note,
.retention-note { margin: 8px 0 0; padding: 8px 10px; border: 1px solid #bcd5f5; border-radius: 6px; color: #39678f; background: #f2f7fd; font-size: 10px; line-height: 14px; }
.retention-note { border-color: #e2d7a4; color: #6e5c20; background: #fffaf0; line-height: 17px; }
.records-title { display: flex; min-height: 30px; align-items: center; justify-content: space-between; margin-top: 8px; }
.records-title strong { color: var(--aima-text); font-size: 12px; }
.records-title :deep(.aima-button) { font-size: 10px; }
.records { max-height: 232px; overflow-y: auto; border: 1px solid var(--aima-border); border-radius: 7px; }
.records article { display: flex; min-height: 114px; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 12px; border-bottom: 1px solid #edf0f4; }
.records article:last-child { border-bottom: 0; }
.record-info { display: grid; min-width: 0; flex: 1; gap: 4px; }
.record-info > strong,
.record-info > small,
.record-info > span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.record-info > strong { color: var(--aima-text); font-size: 11px; }
.record-info > small,
.record-info > span { color: var(--aima-text-muted); font-size: 9px; }
.records :deep(.task-progress) { width: min(280px, 100%); margin-top: 1px; }
.records :deep(.task-progress__heading) { display: none; }
.records :deep(.task-progress__track) { height: 7px; }
.records .error,
.records .expired { color: var(--aima-danger); }
.pending-artifact { color: var(--aima-text-disabled) !important; }
.empty { padding: 24px; color: var(--aima-text-disabled); text-align: center; }
footer { display: flex; min-height: 68px; align-items: center; justify-content: flex-end; gap: 10px; padding: 0 22px; border-top: 1px solid var(--aima-border); }
footer :deep(.aima-button) { height: 38px; }
</style>
