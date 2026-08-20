<script setup lang="ts">
import type { ImportBatchResponse } from '../../../../../generated/api/client'
import { elapsed, formatDateTime, formatNumber, shortId, stageLabels, statusLabels } from '../../../format'

defineProps<{ items: ImportBatchResponse[]; loading: boolean }>()
defineEmits<{ select: [batchId: string] }>()

function statusClass(status: ImportBatchResponse['status']): string {
  return `status status--${status}`
}
</script>

<template>
  <section
    class="batch-list"
    aria-label="导入批次列表"
  >
    <div class="table-head">
      <span>批次 / 来源文件</span><span>状态与进度</span><span>当前阶段</span><span>处理统计</span><span>创建时间 / 耗时</span><span>操作</span>
    </div>
    <div
      v-if="loading && items.length === 0"
      class="table-state"
      role="status"
    >
      正在加载批次…
    </div>
    <div
      v-else-if="items.length === 0"
      class="table-state"
    >
      <strong>暂无导入批次</strong><span>点击“导入 Excel”创建第一个持久化 Import Job。</span>
    </div>
    <article
      v-for="item in items"
      :key="item.id"
      class="table-row"
    >
      <div class="batch-identity">
        <strong>{{ item.source_filename || '未记录源文件名' }}</strong>
        <span>Batch ID: {{ shortId(item.id) }}</span>
      </div>
      <div class="progress-cell">
        <div><i :class="statusClass(item.status)" />{{ statusLabels[item.status] }} <b>{{ item.job.progress }}%</b></div>
        <div class="progress-track">
          <span :style="{ width: `${item.job.progress}%` }" />
        </div>
      </div>
      <div>
        <span
          class="stage-pill"
          :class="`stage-pill--${item.status}`"
        >{{ stageLabels[item.stage] }}</span>
      </div>
      <div class="stats-cell">
        <span>读取<strong>{{ formatNumber(item.stats.rows_seen) }}</strong></span>
        <span>命中<strong>{{ formatNumber(item.stats.rows_matched) }}</strong></span>
        <span>过滤<strong>{{ formatNumber(item.stats.rows_filtered_out) }}</strong></span>
        <span>入库<strong>{{ formatNumber(item.stats.rows_ingested) }}</strong></span>
      </div>
      <div class="time-cell">
        <span>{{ formatDateTime(item.created_at) }}</span><span>{{ elapsed(item.started_at, item.finished_at) }}</span>
      </div>
      <div>
        <button
          class="detail-button"
          type="button"
          @click="$emit('select', item.id)"
        >
          查看详情
        </button>
      </div>
    </article>
  </section>
</template>

<style scoped>
.batch-list { overflow: hidden; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: #fff; }
.table-head, .table-row { display: grid; grid-template-columns: minmax(240px, 1.7fr) minmax(145px, .9fr) minmax(120px, .8fr) minmax(240px, 1.35fr) minmax(150px, .9fr) 100px; align-items: center; }
.table-head { min-height: 48px; padding: 0 16px; border-bottom: 1px solid var(--aima-border); color: #4d5667; background: #fafbfc; font-size: 13px; font-weight: 600; }
.table-row { min-height: 102px; padding: 13px 16px; border-bottom: 1px solid var(--aima-border); }
.table-row:last-child { border-bottom: 0; }
.batch-identity strong, .batch-identity span { display: block; }
.batch-identity strong { overflow: hidden; color: #1f2737; text-overflow: ellipsis; white-space: nowrap; }
.batch-identity span { margin-top: 6px; color: #6d7687; font-size: 12px; }
.progress-cell > div:first-child { display: flex; align-items: center; gap: 7px; color: #414a5b; font-size: 13px; }
.progress-cell b { color: #657087; font-weight: 500; }
.status { width: 7px; height: 7px; border-radius: 50%; background: #94a3b8; }
.status--queued, .status--running { background: #2563eb; }
.status--succeeded { background: var(--aima-success); }
.status--failed { background: var(--aima-danger); }
.progress-track { width: 106px; height: 6px; margin-top: 10px; overflow: hidden; border-radius: 5px; background: #edf0f5; }
.progress-track span { display: block; height: 100%; border-radius: inherit; background: #2563eb; }
.status--succeeded + * { color: var(--aima-success); }
.stage-pill { display: inline-block; padding: 6px 9px; border-radius: 5px; color: #2563eb; background: #eef4ff; font-size: 12px; }
.stage-pill--succeeded { color: #12804b; background: #eaf8f1; }
.stage-pill--failed { color: #d62f3a; background: #fff0f1; }
.stage-pill--cancelled { color: #667085; background: #f1f3f6; }
.stats-cell { display: flex; gap: 15px; }
.stats-cell span, .stats-cell strong { display: block; }
.stats-cell span { color: #737c8c; font-size: 11px; }
.stats-cell strong { margin-top: 5px; color: #263043; font-size: 13px; }
.time-cell span { display: block; color: #3f4859; font-size: 12px; }
.time-cell span + span { margin-top: 7px; color: #718096; }
.detail-button { height: 34px; padding: 0 12px; border: 1px solid var(--aima-primary); border-radius: 6px; color: var(--aima-primary); background: #fff; cursor: pointer; }
.table-state { display: flex; min-height: 240px; flex-direction: column; align-items: center; justify-content: center; color: #8b94a5; }
.table-state strong { margin-bottom: 8px; color: #505a6c; }
</style>
