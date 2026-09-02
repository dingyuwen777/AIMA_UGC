<script setup lang="ts">
import type { CollectionRuntimeItemResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import {
  elapsed,
  formatDateTime,
  formatNumber,
  recordTypeLabels,
  runtimeStageLabel,
  runtimeStatusLabels,
  shortId,
} from '../../../format'

defineProps<{ items: CollectionRuntimeItemResponse[]; loading: boolean }>()
defineEmits<{
  select: [item: CollectionRuntimeItemResponse]
  supplement: [batchId: string]
}>()

function statusClass(item: CollectionRuntimeItemResponse): string {
  return `status-text status-text--${item.status}`
}
</script>

<template>
  <section
    class="runtime-list"
    aria-label="采集运行记录"
  >
    <div class="table-head">
      <span>任务 / 执行编号</span><span>类型</span><span>状态与进度</span><span>当前阶段</span><span>处理统计</span><span>创建时间</span><span>操作</span>
    </div>
    <div
      v-if="loading && items.length === 0"
      class="table-state"
      role="status"
    >
      正在加载运行记录…
    </div>
    <div
      v-else-if="items.length === 0"
      class="table-state"
    >
      <strong>暂无采集运行</strong><span>可从本地电脑或服务器目录导入数据，也可创建辅助补采任务。</span>
    </div>
    <article
      v-for="item in items"
      :key="`${item.record_type}:${item.record_id}`"
      class="table-row"
    >
      <div class="identity">
        <strong>{{ item.display_name }}</strong>
        <span>{{ item.record_type === 'excel_import' ? '批次' : '运行' }} {{ shortId(item.record_id) }}</span>
      </div>
      <div class="type-cell">
        {{ recordTypeLabels[item.record_type] }}
      </div>
      <div class="progress-cell">
        <div :class="statusClass(item)">
          {{ runtimeStatusLabels[item.status] }} · {{ item.progress }}%
        </div>
        <div class="progress-track">
          <span :style="{ width: `${item.progress}%` }" />
        </div>
      </div>
      <div class="stage-cell">
        {{ runtimeStageLabel(item.stage) }}
      </div>
      <div
        v-if="item.import_stats"
        class="stats-cell"
      >
        <span>已读 {{ formatNumber(item.import_stats.rows_seen) }} · 命中 {{ formatNumber(item.import_stats.rows_matched) }}</span>
        <span>过滤 {{ formatNumber(item.import_stats.rows_filtered_out) }} · 入库 {{ formatNumber(item.import_stats.rows_ingested) }}</span>
      </div>
      <div
        v-else
        class="stats-cell"
      >
        <span>请求 {{ formatNumber(item.collection_stats?.requested_count) }} · 成功 {{ formatNumber(item.collection_stats?.succeeded_count) }}</span>
        <span>内容 {{ formatNumber(item.collection_stats?.content_count) }} · 评论 {{ formatNumber(item.collection_stats?.comment_count) }}</span>
      </div>
      <div class="time-cell">
        <span>{{ formatDateTime(item.created_at) }}</span><span>{{ elapsed(item.started_at, item.finished_at) }}</span>
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
          @click="$emit('supplement', item.import_batch_id)"
        >
          基于批次补采
        </AimaButton>
      </div>
      <AimaFeedbackBanner
        v-if="item.error_summary"
        class="row-error"
        tone="error"
        role="alert"
      >
        {{ item.error_summary }}
      </AimaFeedbackBanner>
    </article>
  </section>
</template>

<style scoped>
.runtime-list { overflow: hidden; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: var(--aima-surface); }
.table-head, .table-row { display: grid; grid-template-columns: 180px 120px 235px 134px 175px 130px 110px; align-items: center; column-gap: 16px; }
.table-head { min-height: 44px; padding: 0 16px; border-bottom: 1px solid var(--aima-border); color: var(--aima-text-muted); background: #fafbfc; font-size: 12px; font-weight: 500; }
.table-row { position: relative; min-height: 78px; padding: 16px; border-bottom: 1px solid var(--aima-border); color: var(--aima-text-secondary); font-size: 12px; }
.table-row:nth-of-type(odd) { background: #f8fafc; }
.table-row:last-child { border-bottom: 0; }
.identity strong, .identity span { display: block; }
.identity strong { overflow: hidden; color: var(--aima-text); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.identity span { margin-top: 5px; color: var(--aima-text-muted); font-size: 11px; }
.type-cell, .stage-cell { color: var(--aima-text-secondary); }
.progress-cell { padding-right: 10px; }
.status-text { font-size: 12px; }
.status-text--queued, .status-text--running { color: #1677ff; }
.status-text--succeeded { color: var(--aima-success); }
.status-text--partial_success { color: var(--aima-warning); }
.status-text--failed, .status-text--cancelled { color: var(--aima-danger); }
.progress-track { width: min(100%, 108px); height: 4px; margin-top: 7px; overflow: hidden; border-radius: 4px; background: #edf0f5; }
.progress-track span { display: block; height: 100%; border-radius: inherit; background: #1677ff; }
.stats-cell { display: flex; flex-direction: column; gap: 4px; color: var(--aima-text-secondary); line-height: 18px; }
.time-cell span { display: block; color: var(--aima-text-secondary); font-size: 11px; }
.time-cell span + span { margin-top: 4px; color: var(--aima-text-muted); }
.actions { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.row-error { grid-column: 1 / -1; margin-top: 12px; }
.table-state { display: flex; min-height: 240px; flex-direction: column; align-items: center; justify-content: center; color: var(--aima-text-muted); }
.table-state strong { margin-bottom: 8px; color: var(--aima-text-secondary); }
@media (max-width: 1120px) { .runtime-list { overflow-x: auto; } .table-head, .table-row { min-width: 1212px; } }
</style>
