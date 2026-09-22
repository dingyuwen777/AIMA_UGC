<script setup lang="ts">
import type { CollectionRuntimeItemResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaEmptyState from '../../../../../shared/ui/AimaEmptyState.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import type { SupplementSourceSelection } from '../../../store'
import {
  formatDateTime,
  formatNumber,
  recordTypeLabels,
  runtimeStageLabel,
} from '../../../format'
import CollectionRuntimeStatusProgress from './CollectionRuntimeStatusProgress.vue'

defineProps<{
  items: CollectionRuntimeItemResponse[]
  loading: boolean
  error?: string | null
}>()

defineEmits<{
  select: [item: CollectionRuntimeItemResponse]
  supplement: [source: SupplementSourceSelection]
  retry: []
}>()

/** 列表第二行只展示真实业务来源摘要，不把 Run/Job/Batch 等机器身份暴露到默认视图。 */
function taskSubtitle(item: CollectionRuntimeItemResponse): string {
  if (item.record_type === 'canonical_replay') return '全部历史 Canonical'
  if (item.record_type === 'excel_import') return '本地文件导入'
  if (item.record_type === 'data_import_campaign') return '统一数据导入'
  if (item.record_type === 'tikhub_discovery' && item.keywords?.length) {
    return `关键词：${item.keywords.slice(0, 2).join(' / ')}`
  }
  if (item.record_type === 'tikhub_batch_supplement') return '基于已有导入数据'
  return recordTypeLabels[item.record_type]
}
</script>

<template>
  <section
    class="runtime-list"
    aria-label="采集运行记录"
  >
    <div class="table-head">
      <span>任务</span><span>类型</span><span>状态与进度</span><span>处理环节</span><span>处理结果</span><span>创建时间</span><span>操作</span>
    </div>
    <div
      v-if="loading && items.length === 0"
      class="table-state table-state--loading"
      role="status"
    >
      <AimaFeedbackBanner tone="info">
        正在读取采集运行…
      </AimaFeedbackBanner>
      <div class="skeleton-row" />
      <div class="skeleton-row" />
      <div class="skeleton-row" />
    </div>
    <div
      v-else-if="error && items.length === 0"
      class="table-state table-state--error"
    >
      <AimaFeedbackBanner
        tone="error"
        role="alert"
      >
        采集运行加载失败，请稍后重试。
      </AimaFeedbackBanner>
      <AimaButton
        variant="secondary"
        size="small"
        @click="$emit('retry')"
      >
        重试
      </AimaButton>
    </div>
    <div
      v-else-if="items.length === 0"
      class="table-state table-state--empty"
    >
      <AimaEmptyState
        title="暂无采集运行"
        description="可导入数据，或创建一次辅助补采任务。"
      />
    </div>
    <article
      v-for="item in items"
      :key="`${item.record_type}:${item.record_id}`"
      class="table-row"
    >
      <div class="identity">
        <strong>{{ item.display_name }}</strong>
        <span>{{ taskSubtitle(item) }}</span>
      </div>
      <div class="type-cell">
        {{ recordTypeLabels[item.record_type] }}
      </div>
      <div class="progress-cell">
        <CollectionRuntimeStatusProgress
          :status="item.status"
          :progress="item.progress"
        />
      </div>
      <div class="stage-cell">
        {{ runtimeStageLabel(item.stage) }}
      </div>
      <div
        v-if="item.canonical_replay_stats"
        class="stats-cell"
      >
        <span>完成 {{ formatNumber(item.canonical_replay_stats.succeeded_run_count + item.canonical_replay_stats.failed_run_count + item.canonical_replay_stats.cancelled_run_count) }} / {{ formatNumber(item.canonical_replay_stats.run_count) }} 个子任务</span>
        <span>入库 {{ formatNumber(item.canonical_replay_stats.rows_ingested) }} 条</span>
      </div>
      <div
        v-else-if="item.import_stats"
        class="stats-cell"
      >
        <span>匹配 {{ formatNumber(item.import_stats.rows_matched) }} 条</span>
        <span>入库 {{ formatNumber(item.import_stats.rows_ingested) }} 条</span>
      </div>
      <div
        v-else
        class="stats-cell"
      >
        <span>{{ item.status === 'succeeded' ? '采集完成' : `完成 ${formatNumber(item.collection_stats?.succeeded_count)} · 失败 ${formatNumber(item.collection_stats?.failed_count)}` }}</span>
        <span>内容 {{ formatNumber(item.collection_stats?.content_count) }} · 评论 {{ formatNumber(item.collection_stats?.comment_count) }}</span>
      </div>
      <div class="time-cell">
        {{ formatDateTime(item.created_at) }}
      </div>
      <div class="actions">
        <AimaButton
          variant="text"
          size="small"
          @click="$emit('select', item)"
        >
          查看详情
        </AimaButton>
        <AimaButton
          v-if="item.record_type === 'excel_import' && item.import_batch_id && item.status === 'succeeded' && (item.import_stats?.rows_ingested ?? 0) > 0"
          variant="text"
          size="small"
          @click="$emit('supplement', { kind: 'batch', id: item.import_batch_id })"
        >
          基于本次导入补采
        </AimaButton>
        <AimaButton
          v-if="item.record_type === 'data_import_campaign' && item.data_import_campaign_id && ['succeeded', 'partial_success'].includes(item.status) && (item.import_stats?.rows_matched ?? 0) > 0"
          variant="text"
          size="small"
          @click="$emit('supplement', { kind: 'campaign', id: item.data_import_campaign_id })"
        >
          基于本次导入补采
        </AimaButton>
      </div>
    </article>
  </section>
</template>

<style scoped>
.runtime-list { overflow-x: auto; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.table-head, .table-row { display: grid; min-width: 1212px; grid-template-columns: minmax(180px, 1fr) 120px minmax(235px, 1fr) 134px 175px 130px 110px; align-items: center; column-gap: 16px; }
.table-head { min-height: 44px; padding: 0 16px; border-bottom: 1px solid var(--aima-border); color: var(--aima-text-muted); background: var(--aima-color-bg-table-header); font-size: 12px; font-weight: 500; }
.table-head span { text-align: center; }
.table-row { position: relative; min-height: 78px; padding: 16px; border-bottom: 1px solid var(--aima-border); color: var(--aima-text-secondary); font-size: 13px; line-height: 20px; }
.table-row:nth-of-type(even) { background: var(--aima-color-bg-subtle); }
.table-row:last-child { border-bottom: 0; }
.identity { min-width: 0; text-align: center; }
.identity strong, .identity span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.identity strong { color: var(--aima-text); font-size: 14px; font-weight: 700; line-height: 20px; }
.identity span { margin-top: 4px; color: var(--aima-text-secondary); font-size: 12px; line-height: 18px; }
.type-cell, .stage-cell, .time-cell { color: var(--aima-text-secondary); text-align: center; }
.progress-cell { min-width: 0; }
.stats-cell { display: flex; flex-direction: column; gap: 4px; color: var(--aima-text-secondary); text-align: center; }
.stats-cell span + span { font-size: 12px; line-height: 18px; }
.time-cell { font-size: 13px; }
.actions { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.actions :deep(.aima-button.is-text) { min-width: 76px; color: var(--aima-color-info); }
.table-state { min-width: 0; padding: 16px; }
.table-state--loading { display: grid; gap: 10px; min-height: 178px; align-content: center; }
.table-state--loading :deep(.aima-feedback) { width: min(100%, 560px); }
.skeleton-row { width: 100%; height: 20px; border-radius: var(--aima-radius-sm); background: var(--aima-color-bg-subtle); }
.table-state--error { display: grid; min-height: 178px; gap: 20px; align-content: center; justify-items: end; }
.table-state--error :deep(.aima-feedback) { width: 100%; }
.table-state--error :deep(.aima-button) { min-width: 92px; }
.table-state--empty { min-height: 196px; }
.table-state--empty :deep(.aima-empty-state) { width: min(100%, 420px); margin: 0 auto; }
</style>
