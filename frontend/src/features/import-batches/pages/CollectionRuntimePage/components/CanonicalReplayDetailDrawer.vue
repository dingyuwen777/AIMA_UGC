<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { CollectionRuntimeItemResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaDialog from '../../../../../shared/ui/AimaDialog.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaModalContainer from '../../../../../shared/ui/AimaModalContainer.vue'
import {
  elapsed,
  formatDateTime,
  formatNumber,
  runtimeFailureMessage,
  runtimeStageLabel,
  runtimeStatusLabels,
} from '../../../format'

const props = defineProps<{
  modelValue: boolean
  item: CollectionRuntimeItemResponse | null
  acting?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  refresh: []
  copy: [value: string]
  'cancel-and-revoke': []
  revoke: []
}>()
const activeTab = ref<'overview' | 'status' | 'errors'>('overview')
const confirmationOpen = ref(false)

watch(
  () => props.item?.record_id,
  () => {
    activeTab.value = 'overview'
  },
)

const stats = computed(() => props.item?.canonical_replay_stats ?? null)
const terminalRunCount = computed(() => {
  const value = stats.value
  if (!value) return 0
  return value.succeeded_run_count + value.failed_run_count + value.cancelled_run_count
})
const actionKind = computed<'cancel-and-revoke' | 'revoke' | null>(() => {
  const item = props.item
  const value = stats.value
  if (!item || !value?.reversible) return null
  if (value.lifecycle_status === 'revert_failed') return 'revoke'
  if (value.lifecycle_status !== 'active') return null
  return item.status === 'queued' || item.status === 'running' ? 'cancel-and-revoke' : 'revoke'
})
const actionLabel = computed(() => {
  if (stats.value?.lifecycle_status === 'revert_failed') return '重试撤回'
  return actionKind.value === 'cancel-and-revoke' ? '取消并撤回' : '撤回本次入库'
})

function confirmAction(): void {
  confirmationOpen.value = false
  if (actionKind.value === 'cancel-and-revoke') emit('cancel-and-revoke')
  else if (actionKind.value === 'revoke') emit('revoke')
}

function failureMessage(item: CollectionRuntimeItemResponse): string {
  if ((stats.value?.failed_run_count ?? 0) > 0) {
    return `${formatNumber(stats.value?.failed_run_count)} 个重筛子任务失败；其他子任务结果已经保留。`
  }
  return runtimeFailureMessage(item.error_code ?? item.error_summary) ?? '重筛任务执行遇到问题。'
}
</script>

<template>
  <AimaModalContainer
    :model-value="modelValue"
    label="重筛详情"
    width="820px"
    height="780px"
    :close-disabled="acting"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <template v-if="item">
        <header class="drawer-header">
          <strong>重筛详情</strong>
          <AimaButton
            variant="text"
            size="small"
            aria-label="关闭详情"
            @click="emit('update:modelValue', false)"
          >
            关闭
          </AimaButton>
        </header>
        <nav
          class="detail-tabs"
          aria-label="重筛详情标签页"
        >
          <button
            type="button"
            :class="{ active: activeTab === 'overview' }"
            @click="activeTab = 'overview'"
          >
            运行概览
          </button>
          <button
            type="button"
            :class="{ active: activeTab === 'status' }"
            @click="activeTab = 'status'"
          >
            任务信息
          </button>
          <button
            type="button"
            :class="{ active: activeTab === 'errors' }"
            @click="activeTab = 'errors'"
          >
            问题记录
          </button>
        </nav>
      </template>
    </template>

    <div
      v-if="item && stats"
      class="drawer-content"
    >
      <section
        v-if="activeTab === 'overview'"
        class="tab-content"
      >
        <div class="detail-title">
          <h2>{{ item.display_name }}</h2>
          <span :class="`status-tag status-tag--${item.status}`">{{ runtimeStatusLabels[item.status] }}</span>
        </div>
        <div class="fact-grid">
          <div><span>处理范围</span><strong>全部历史 Canonical</strong></div>
          <div><span>创建时间</span><strong>{{ formatDateTime(item.created_at) }}</strong></div>
          <div><span>Canonical 文件</span><strong>{{ formatNumber(stats.artifact_count) }}</strong></div>
          <div><span>总耗时</span><strong>{{ elapsed(item.started_at, item.finished_at) }}</strong></div>
        </div>
        <div class="progress-panel">
          <div><strong>总体进度</strong><span>{{ item.progress }}%</span></div>
          <div class="detail-progress">
            <span :style="{ width: `${Math.max(0, Math.min(100, item.progress))}%` }" />
          </div>
          <small>已结束 {{ formatNumber(terminalRunCount) }} / {{ formatNumber(stats.run_count) }} 个子任务</small>
        </div>
        <h3>处理统计</h3>
        <div class="stat-grid">
          <div><span>读取行</span><strong>{{ formatNumber(stats.rows_seen) }}</strong></div>
          <div><span>相关命中</span><strong>{{ formatNumber(stats.rows_matched) }}</strong></div>
          <div><span>已过滤</span><strong>{{ formatNumber(stats.rows_filtered_out) }}</strong></div>
          <div><span>去重</span><strong>{{ formatNumber(stats.duplicates_removed) }}</strong></div>
          <div><span>新增记录</span><strong>{{ formatNumber(stats.rows_ingested) }}</strong></div>
          <div><span>处理已有记录</span><strong>{{ formatNumber(stats.existing_convergence) }}</strong></div>
        </div>
        <AimaFeedbackBanner
          class="info-note"
          tone="info"
        >
          处理已有记录按输入记录累计；同一内容在不同来源重复出现时会分别计数。撤回统计按不同内容计数。
        </AimaFeedbackBanner>
        <template v-if="['reverting', 'reverted', 'revert_failed'].includes(stats.lifecycle_status)">
          <h3>撤回统计</h3>
          <div class="stat-grid">
            <div><span>已重算内容</span><strong>{{ formatNumber(stats.reverted_content_count) }}</strong></div>
            <div><span>已隐藏</span><strong>{{ formatNumber(stats.hidden_content_count) }}</strong></div>
            <div><span>保留共享/后写</span><strong>{{ formatNumber(stats.retained_content_count) }}</strong></div>
            <div><span>跳过内容</span><strong>{{ formatNumber(stats.skipped_content_count) }}</strong></div>
            <div><span>已恢复证据</span><strong>{{ formatNumber(stats.restored_evidence_count) }}</strong></div>
            <div><span>保护性跳过证据</span><strong>{{ formatNumber(stats.skipped_evidence_count) }}</strong></div>
          </div>
        </template>
      </section>

      <section
        v-else-if="activeTab === 'status'"
        class="tab-content"
      >
        <h3>任务信息</h3>
        <div class="fact-grid fact-grid--single">
          <div><span>当前状态</span><strong>{{ runtimeStatusLabels[item.status] }}</strong></div>
          <div><span>处理环节</span><strong>{{ runtimeStageLabel(item.stage) }}</strong></div>
          <div><span>开始时间</span><strong>{{ formatDateTime(item.started_at) }}</strong></div>
          <div><span>结束时间</span><strong>{{ formatDateTime(item.finished_at) }}</strong></div>
          <div><span>子任务结束</span><strong>{{ formatNumber(terminalRunCount) }} / {{ formatNumber(stats.run_count) }}</strong></div>
          <div><span>成功 / 失败 / 取消</span><strong>{{ formatNumber(stats.succeeded_run_count) }} / {{ formatNumber(stats.failed_run_count) }} / {{ formatNumber(stats.cancelled_run_count) }}</strong></div>
        </div>
        <AimaFeedbackBanner
          class="info-note"
          tone="info"
        >
          详情会跟随采集运行记录自动刷新；关闭页面后重筛任务仍会继续在后台执行。
        </AimaFeedbackBanner>
        <AimaFeedbackBanner
          v-if="!stats.reversible"
          class="info-note"
          tone="info"
        >
          这条记录创建于精确贡献账本启用前，系统不会猜测历史写入，因此不能撤回。
        </AimaFeedbackBanner>
        <details class="technical-details">
          <summary>技术详情</summary>
          <div class="technical-grid">
            <div>
              <span>重筛请求 ID</span><code>{{ item.canonical_replay_request_id }}</code><button
                v-if="item.canonical_replay_request_id"
                type="button"
                @click="emit('copy', item.canonical_replay_request_id)"
              >
                复制
              </button>
            </div>
            <div><span>记录类型</span><code>{{ item.record_type }}</code></div>
            <div><span>排队 / 运行</span><code>{{ stats.queued_run_count }} / {{ stats.running_run_count }}</code></div>
            <div><span>撤回状态</span><code>{{ stats.lifecycle_status }}</code></div>
            <div v-if="stats.reversal_job_id">
              <span>撤回任务 ID</span><code>{{ stats.reversal_job_id }}</code>
            </div>
          </div>
        </details>
      </section>

      <section
        v-else
        class="tab-content"
      >
        <h3>问题记录</h3>
        <AimaFeedbackBanner
          v-if="item.error_code || item.error_summary || stats.failed_run_count > 0"
          tone="error"
          role="alert"
        >
          {{ failureMessage(item) }}
        </AimaFeedbackBanner>
        <div
          v-else
          class="empty-error"
        >
          当前没有问题记录。
        </div>
        <details
          v-if="item.error_code || item.error_summary"
          class="technical-details"
        >
          <summary>技术详情</summary>
          <div class="technical-grid">
            <div v-if="item.error_code">
              <span>错误码</span><code>{{ item.error_code }}</code>
            </div>
            <div v-if="item.error_summary">
              <span>错误摘要</span><code>{{ item.error_summary }}</code>
            </div>
          </div>
        </details>
      </section>
    </div>

    <template #footer>
      <footer
        v-if="item"
        class="drawer-footer"
      >
        <AimaButton
          v-if="actionKind"
          class="danger-action"
          variant="secondary"
          :disabled="acting"
          @click="confirmationOpen = true"
        >
          {{ actionLabel }}
        </AimaButton>
        <AimaButton
          variant="primary"
          :disabled="acting"
          @click="emit('refresh')"
        >
          刷新详情
        </AimaButton>
      </footer>
    </template>
  </AimaModalContainer>

  <AimaDialog
    v-model="confirmationOpen"
    width="500px"
    label="确认撤回历史重筛"
    :dismissible="!acting"
  >
    <template #header>
      <strong>确认{{ actionLabel }}？</strong>
    </template>
    <p>
      系统会保留 Canonical、Raw、Content 历史版本与审计记录，仅撤回仍能证明属于本次重筛的 Current
      字段、业务可见性和自动品牌/车型证据；人工锁定及后续其他来源写入不会被覆盖。
    </p>
    <template #footer>
      <AimaButton
        variant="secondary"
        size="small"
        :disabled="acting"
        @click="confirmationOpen = false"
      >
        返回
      </AimaButton>
      <AimaButton
        class="danger-action"
        variant="secondary"
        size="small"
        :disabled="acting"
        @click="confirmAction"
      >
        {{ acting ? '提交中…' : '确认撤回' }}
      </AimaButton>
    </template>
  </AimaDialog>
</template>

<style scoped>
.drawer-header { display: flex; height: 60px; align-items: center; justify-content: space-between; padding: 0 20px; border-bottom: 1px solid var(--aima-border); background: var(--aima-surface); }
.drawer-header strong { color: var(--aima-text); font-size: 17px; font-weight: 700; line-height: 24px; }
.detail-tabs { display: grid; height: 44px; grid-template-columns: repeat(3, 1fr); padding: 0 10px; border-bottom: 1px solid var(--aima-border); background: var(--aima-surface); }
.detail-tabs button { height: 44px; padding: 0 4px; border: 0; border-bottom: 2px solid transparent; color: var(--aima-text-muted); background: transparent; cursor: pointer; font-size: 13px; line-height: 20px; }
.detail-tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 500; }
.drawer-content { min-height: 560px; padding: 8px 22px 16px; }
.detail-title { display: flex; min-height: 42px; align-items: center; justify-content: space-between; gap: 10px; }
.detail-title h2 { margin: 0; color: var(--aima-text); font-size: 18px; line-height: 26px; }
.status-tag { flex: none; padding: 4px 10px; border-radius: 6px; color: var(--aima-color-info); background: var(--aima-color-bg-subtle); font-size: 12px; white-space: nowrap; }
.status-tag--succeeded { color: var(--aima-success); }
.status-tag--partial_success { color: var(--aima-color-warning); background: var(--aima-color-warning-bg); }
.status-tag--failed, .status-tag--cancelled { color: var(--aima-danger); background: var(--aima-color-error-bg); }
.fact-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; padding: 16px 0; }
.fact-grid > div { min-width: 0; padding: 10px 12px; border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.fact-grid span, .fact-grid strong { display: block; }
.fact-grid span { color: var(--aima-color-text-tertiary); font-size: 12px; line-height: 18px; }
.fact-grid strong { overflow: hidden; margin-top: 8px; color: var(--aima-text); font-size: 16px; line-height: 22px; text-overflow: ellipsis; white-space: nowrap; }
.fact-grid--single { grid-template-columns: 1fr; }
.progress-panel { padding: 12px; border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.progress-panel > div:first-child { display: flex; justify-content: space-between; color: var(--aima-text); font-size: 12px; line-height: 18px; }
.progress-panel > div:first-child span { color: var(--aima-primary); font-weight: 700; }
.progress-panel small { display: block; margin-top: 8px; color: var(--aima-text-muted); }
.detail-progress { height: 8px; margin-top: 12px; overflow: hidden; border-radius: 4px; background: var(--aima-color-bg-subtle); }
.detail-progress span { display: block; height: 100%; border-radius: inherit; background: var(--aima-primary); }
h3 { margin: 16px 0 10px; color: var(--aima-text); font-size: 14px; font-weight: 500; line-height: 20px; }
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.stat-grid div { min-height: 64px; padding: 12px; border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.stat-grid span, .stat-grid strong { display: block; }
.stat-grid span { color: var(--aima-color-text-tertiary); font-size: 10px; line-height: 16px; }
.stat-grid strong { margin-top: 4px; color: var(--aima-primary); font-size: 16px; line-height: 22px; }
.info-note { margin-top: 20px; }
.empty-error { padding: 54px 0; color: var(--aima-text-muted); text-align: center; font-size: 12px; }
.technical-details { margin-top: 20px; padding-top: 12px; border-top: 1px solid var(--aima-border); color: var(--aima-text-muted); font-size: 11px; }
.technical-details summary { width: max-content; cursor: pointer; font-size: 12px; }
.technical-grid { display: grid; gap: 8px; margin-top: 12px; }
.technical-grid > div { display: grid; grid-template-columns: 92px minmax(0, 1fr) auto; align-items: center; gap: 8px; }
.technical-grid code { overflow-wrap: anywhere; color: var(--aima-text-secondary); font-size: 10px; }
.technical-grid button { border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 10px; }
.drawer-footer { display: flex; height: 72px; align-items: center; justify-content: flex-end; gap: 10px; padding: 0 20px; border-top: 1px solid var(--aima-border); background: var(--aima-surface); }
.drawer-footer :deep(.aima-button.is-primary) { min-width: 104px; }
.danger-action { border-color: var(--aima-danger); color: var(--aima-danger); }
:global(.aima-dialog[aria-label='确认撤回历史重筛'] .aima-dialog-header) { padding: 18px 20px 8px; }
:global(.aima-dialog[aria-label='确认撤回历史重筛'] .aima-dialog-body) { padding: 8px 20px 18px; color: var(--aima-text-secondary); font-size: 13px; line-height: 22px; }
:global(.aima-dialog[aria-label='确认撤回历史重筛'] .aima-dialog-footer) { display: flex; justify-content: flex-end; gap: 10px; padding: 12px 20px 18px; }
</style>
