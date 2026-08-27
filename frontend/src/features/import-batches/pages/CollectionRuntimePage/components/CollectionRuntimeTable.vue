<script setup lang="ts">
import type { CollectionRuntimeItemResponse } from '../../../../../generated/api/client'
import {
  elapsed,
  formatDateTime,
  formatNumber,
  platformLabels,
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
  return `status status--${item.status}`
}
</script>

<template>
  <section
    class="runtime-list"
    aria-label="采集运行记录"
  >
    <div class="table-head">
      <span>任务 / 执行 ID</span><span>类型</span><span>状态与进度</span><span>当前阶段</span><span>处理统计</span><span>关联对象</span><span>创建时间</span><span>操作</span>
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
      <strong>暂无采集运行</strong><span>可从本地电脑或服务器目录导入数据，也可创建一次 TikHub 辅助补采。</span>
    </div>
    <article
      v-for="item in items"
      :key="`${item.record_type}:${item.record_id}`"
      class="table-row"
    >
      <div class="identity">
        <strong>{{ item.display_name }}</strong>
        <span>{{ item.record_type === 'excel_import' ? 'Batch' : 'Run' }} ID: {{ shortId(item.record_id) }}</span>
      </div>
      <div><span :class="`type-pill type-pill--${item.record_type}`">{{ recordTypeLabels[item.record_type] }}</span></div>
      <div class="progress-cell">
        <div><i :class="statusClass(item)" />{{ runtimeStatusLabels[item.status] }} <b>{{ item.progress }}%</b></div>
        <div class="progress-track">
          <span :style="{ width: `${item.progress}%` }" />
        </div>
      </div>
      <div><span class="stage-pill">{{ runtimeStageLabel(item.stage) }}</span></div>
      <div
        v-if="item.import_stats"
        class="stats-cell"
      >
        <span>读取<strong>{{ formatNumber(item.import_stats.rows_seen) }}</strong></span>
        <span>命中<strong>{{ formatNumber(item.import_stats.rows_matched) }}</strong></span>
        <span>过滤<strong>{{ formatNumber(item.import_stats.rows_filtered_out) }}</strong></span>
        <span>入库<strong>{{ formatNumber(item.import_stats.rows_ingested) }}</strong></span>
      </div>
      <div
        v-else
        class="stats-cell"
      >
        <span>请求<strong>{{ formatNumber(item.collection_stats?.requested_count) }}</strong></span>
        <span>成功<strong>{{ formatNumber(item.collection_stats?.succeeded_count) }}</strong></span>
        <span>内容<strong>{{ formatNumber(item.collection_stats?.content_count) }}</strong></span>
        <span>评论<strong>{{ formatNumber(item.collection_stats?.comment_count) }}</strong></span>
      </div>
      <div class="related">
        <template v-if="item.import_batch_id">
          <span>Batch ID</span><strong>{{ shortId(item.import_batch_id) }}</strong>
        </template>
        <template v-else>
          <span>平台</span><strong>{{ item.platforms?.map((platform) => platformLabels[platform]).join(' / ') || '—' }}</strong>
        </template>
      </div>
      <div class="time-cell">
        <span>{{ formatDateTime(item.created_at) }}</span><span>{{ elapsed(item.started_at, item.finished_at) }}</span>
      </div>
      <div class="actions">
        <button
          type="button"
          @click="$emit('select', item)"
        >
          查看详情
        </button>
        <button
          v-if="item.record_type === 'excel_import' && item.import_batch_id && item.status === 'succeeded' && (item.import_stats?.rows_ingested ?? 0) > 0"
          type="button"
          @click="$emit('supplement', item.import_batch_id)"
        >
          基于批次补采
        </button>
      </div>
      <div
        v-if="item.error_summary"
        class="row-error"
      >
        ⚠ {{ item.error_summary }}
      </div>
    </article>
  </section>
</template>

<style scoped>
.runtime-list { overflow: hidden; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: #fff; }
.table-head, .table-row { display: grid; grid-template-columns: minmax(205px, 1.4fr) 100px minmax(135px, .85fr) 120px minmax(210px, 1.25fr) minmax(135px, .85fr) 130px 116px; align-items: center; }
.table-head { min-height: 46px; padding: 0 14px; border-bottom: 1px solid var(--aima-border); color: #4d5667; background: #fafbfc; font-size: 12px; font-weight: 600; }
.table-row { position: relative; min-height: 96px; padding: 13px 14px; border-bottom: 1px solid var(--aima-border); }.table-row:last-child { border-bottom: 0; }
.identity strong, .identity span { display: block; }.identity strong { overflow: hidden; color: #1f2737; text-overflow: ellipsis; white-space: nowrap; }.identity span { margin-top: 6px; color: #6d7687; font-size: 11px; }
.type-pill { display: inline-block; padding: 5px 8px; border-radius: 5px; color: #12804b; background: #eaf8f1; font-size: 11px; }.type-pill--tikhub_discovery { color: #6941c6; background: #f2edff; }.type-pill--tikhub_batch_supplement { color: #b54708; background: #fff3e8; }
.progress-cell > div:first-child { display: flex; align-items: center; gap: 6px; color: #414a5b; font-size: 12px; }.progress-cell b { color: #657087; font-weight: 500; }.status { width: 7px; height: 7px; border-radius: 50%; background: #94a3b8; }.status--queued, .status--running { background: #2563eb; }.status--succeeded { background: var(--aima-success); }.status--partial_success { background: var(--aima-warning); }.status--failed { background: var(--aima-danger); }
.progress-track { width: 100px; height: 5px; margin-top: 9px; overflow: hidden; border-radius: 5px; background: #edf0f5; }.progress-track span { display: block; height: 100%; border-radius: inherit; background: #2563eb; }.stage-pill { display: inline-block; padding: 5px 8px; border-radius: 5px; color: #2563eb; background: #eef4ff; font-size: 11px; }
.stats-cell { display: flex; gap: 11px; }.stats-cell span, .stats-cell strong { display: block; }.stats-cell span { color: #737c8c; font-size: 10px; }.stats-cell strong { margin-top: 4px; color: #263043; font-size: 12px; }
.related span, .related strong, .time-cell span { display: block; font-size: 11px; }.related span, .time-cell span + span { color: #718096; }.related strong { margin-top: 5px; color: #3f4859; font-weight: 500; }.time-cell span { color: #3f4859; }.time-cell span + span { margin-top: 6px; }
.actions { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }.actions button { height: 29px; padding: 0 9px; border: 1px solid #ff85af; border-radius: 5px; color: var(--aima-primary); background: #fff; cursor: pointer; font-size: 11px; }
.row-error { grid-column: 1 / -1; margin-top: 10px; padding: 8px 10px; border: 1px solid #ffb8c5; border-radius: 5px; color: #d62f3a; background: #fff5f7; font-size: 11px; }.table-state { display: flex; min-height: 240px; flex-direction: column; align-items: center; justify-content: center; color: #8b94a5; }.table-state strong { margin-bottom: 8px; color: #505a6c; }
</style>
