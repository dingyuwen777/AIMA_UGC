<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { ImportBatchResponse, ImportStage } from '../../../../../generated/api/client'
import { elapsed, formatDateTime, formatNumber, shortId, stageLabels, statusLabels } from '../../../format'

const props = defineProps<{ modelValue: boolean; item: ImportBatchResponse | null }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  refresh: []
  copy: [value: string]
  viewContents: [batchId: string]
}>()
const activeTab = ref('overview')

watch(
  () => props.item?.id,
  () => {
    activeTab.value = 'overview'
  },
)

const stageOrder: ImportStage[] = ['reading', 'mapping', 'filtering', 'deduplicating', 'ingesting']
const stageRows = computed(() => {
  const current = props.item?.stage ?? 'queued'
  const currentIndex = stageOrder.indexOf(current)
  return stageOrder.map((stage, index) => ({
    stage,
    state:
      current === 'succeeded'
        ? 'done'
        : current === 'failed' || current === 'cancelled'
          ? 'pending'
          : index < currentIndex
            ? 'done'
            : index === currentIndex
              ? 'current'
              : 'pending',
  }))
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="drawer-layer"
      role="presentation"
      @click.self="emit('update:modelValue', false)"
    >
      <aside
        class="drawer"
        role="dialog"
        aria-modal="true"
        aria-label="批次详情"
      >
        <template v-if="item">
          <header class="drawer-header">
            <strong>批次详情</strong><button
              type="button"
              aria-label="关闭详情"
              @click="emit('update:modelValue', false)"
            >
              ×
            </button>
          </header>
          <nav
            class="detail-tabs"
            aria-label="详情标签页"
          >
            <button
              v-for="tab in [{ name: 'overview', label: '运行概览' }, { name: 'stages', label: '处理阶段' }, { name: 'job', label: 'Job 状态' }, { name: 'errors', label: '错误记录' }]"
              :key="tab.name"
              type="button"
              :class="{ active: activeTab === tab.name }"
              @click="activeTab = tab.name"
            >
              {{ tab.label }}
            </button>
          </nav>

          <section
            v-if="activeTab === 'overview'"
            class="tab-content"
          >
            <div class="detail-title">
              <h2>{{ item.source_filename || 'Excel 导入批次' }}</h2><span :class="`status-tag status-tag--${item.status}`">{{ statusLabels[item.status] }}</span>
            </div>
            <div class="fact-grid">
              <div>
                <span>Batch ID</span><strong>{{ shortId(item.id) }} <button
                  type="button"
                  @click="emit('copy', item.id)"
                >▢</button></strong>
              </div>
              <div>
                <span>Job ID</span><strong>{{ shortId(item.job.id) }} <button
                  type="button"
                  @click="emit('copy', item.job.id)"
                >▢</button></strong>
              </div>
              <div><span>来源文件</span><strong>{{ item.source_filename || '—' }}</strong></div>
              <div><span>创建时间</span><strong>{{ formatDateTime(item.created_at) }}</strong></div>
              <div><span>Attempt</span><strong>{{ item.job.attempt }} / {{ item.job.max_attempts }}</strong></div>
              <div><span>总耗时</span><strong>{{ elapsed(item.started_at, item.finished_at) }}</strong></div>
            </div>
            <div class="progress-panel">
              <div><strong>总体进度</strong><span>{{ item.job.progress }}%</span></div><div class="detail-progress">
                <span :style="{ width: `${item.job.progress}%` }" />
              </div>
            </div>
            <h3>处理统计</h3>
            <div class="stat-grid">
              <div><span>读取行</span><strong>{{ formatNumber(item.stats.rows_seen) }}</strong></div>
              <div><span>相关命中</span><strong>{{ formatNumber(item.stats.rows_matched) }}</strong></div>
              <div><span>已过滤</span><strong>{{ formatNumber(item.stats.rows_filtered_out) }}</strong></div>
              <div><span>去重</span><strong>{{ formatNumber(item.stats.duplicates_removed) }}</strong></div>
              <div><span>已入库</span><strong>{{ formatNumber(item.stats.rows_ingested) }}</strong></div>
              <div><span>拒绝</span><strong>{{ formatNumber(item.stats.rows_rejected) }}</strong></div>
            </div>
          </section>

          <section
            v-else-if="activeTab === 'stages'"
            class="tab-content"
          >
            <h3>处理阶段</h3>
            <div class="stage-list">
              <div class="stage-row stage-row--done">
                <i>✓</i><span>上传与 Artifact</span><b>成功</b>
              </div>
              <div
                v-for="row in stageRows"
                :key="row.stage"
                class="stage-row"
                :class="`stage-row--${row.state}`"
              >
                <i>{{ row.state === 'done' ? '✓' : row.state === 'current' ? '•' : '○' }}</i><span>{{ stageLabels[row.stage] }}</span><b>{{ row.state === 'done' ? '完成' : row.state === 'current' ? '进行中' : '等待中' }}</b>
              </div>
            </div>
          </section>

          <section
            v-else-if="activeTab === 'job'"
            class="tab-content"
          >
            <h3>持久化 Import Job</h3>
            <div class="fact-grid fact-grid--single">
              <div><span>Job 类型</span><strong>{{ item.job.job_type }}</strong></div>
              <div><span>状态</span><strong>{{ statusLabels[item.job.status] }}</strong></div>
              <div><span>开始时间</span><strong>{{ formatDateTime(item.job.started_at) }}</strong></div>
              <div><span>结束时间</span><strong>{{ formatDateTime(item.job.finished_at) }}</strong></div>
            </div>
            <p class="info-note">
              详情每 5 秒自动刷新；关闭页面后 Job 仍由 Worker 持续执行。
            </p>
          </section>

          <section
            v-else
            class="tab-content"
          >
            <h3>安全错误摘要</h3>
            <div
              v-if="item.error_summary"
              class="error-card"
            >
              <strong>{{ item.job.error_code || 'import_failed' }}</strong><p>{{ item.error_summary }}</p>
            </div>
            <div
              v-else
              class="empty-error"
            >
              当前没有错误记录。
            </div>
          </section>

          <footer class="drawer-footer">
            <button
              type="button"
              @click="emit('copy', item.id)"
            >
              复制 Batch ID
            </button><button
              type="button"
              :disabled="item.stats.rows_ingested === 0"
              @click="emit('viewContents', item.id)"
            >
              查看处理内容
            </button><button
              class="primary"
              type="button"
              @click="emit('refresh')"
            >
              刷新详情
            </button>
          </footer>
        </template>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer-layer { position: fixed; inset: 0; z-index: 100; background: rgb(22 29 43 / 40%); }
.drawer { position: absolute; inset: 0 0 0 auto; width: 470px; overflow-y: auto; padding: 0 20px; background: #fff; box-shadow: -10px 0 30px rgb(23 32 51 / 12%); }
.drawer-header { display: flex; height: 58px; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--aima-border); }
.drawer-header strong { font-size: 17px; }
.drawer-header button { border: 0; color: #475166; background: transparent; cursor: pointer; font-size: 25px; }
.detail-tabs { display: grid; grid-template-columns: repeat(4, 1fr); border-bottom: 1px solid var(--aima-border); }
.detail-tabs button { height: 50px; border: 0; border-bottom: 2px solid transparent; color: #596275; background: transparent; cursor: pointer; }
.detail-tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 600; }
.tab-content { padding-bottom: 76px; }
.detail-title { display: flex; align-items: center; gap: 10px; }
.detail-title h2 { margin: 10px 0 15px; font-size: 18px; }
.status-tag { padding: 4px 8px; border-radius: 4px; color: #2563eb; background: #eef4ff; font-size: 12px; white-space: nowrap; }
.status-tag--succeeded { color: #12804b; background: #eaf8f1; }
.status-tag--failed { color: #d62f3a; background: #fff0f1; }
.fact-grid { display: grid; grid-template-columns: 1fr 1fr; overflow: hidden; border: 1px solid var(--aima-border); border-radius: 8px; }
.fact-grid > div { min-height: 69px; padding: 13px; border-right: 1px solid var(--aima-border); border-bottom: 1px solid var(--aima-border); }
.fact-grid > div:nth-child(2n) { border-right: 0; }
.fact-grid > div:nth-last-child(-n + 2) { border-bottom: 0; }
.fact-grid span, .fact-grid strong { display: block; }
.fact-grid span { color: #778093; font-size: 12px; }
.fact-grid strong { overflow: hidden; margin-top: 8px; color: #263043; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.fact-grid button { border: 0; color: #687386; background: transparent; cursor: pointer; }
.fact-grid--single { grid-template-columns: 1fr; }
.fact-grid--single > div { border-right: 0; }
.fact-grid--single > div:nth-last-child(-n + 2) { border-bottom: 1px solid var(--aima-border); }
.fact-grid--single > div:last-child { border-bottom: 0; }
.progress-panel { margin: 14px 0; padding: 14px; border: 1px solid var(--aima-border); border-radius: 8px; }
.progress-panel > div { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 13px; }
.detail-progress { height: 7px; overflow: hidden; border-radius: 5px; background: #edf1f7; }
.detail-progress span { display: block; height: 100%; border-radius: inherit; background: #2563eb; }
h3 { margin: 18px 0 12px; font-size: 14px; }
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.stat-grid div { padding: 12px 8px; border: 1px solid var(--aima-border); border-radius: 6px; text-align: center; }
.stat-grid span, .stat-grid strong { display: block; }
.stat-grid span { color: #737c8d; font-size: 11px; }
.stat-grid strong { margin-top: 5px; color: #2563eb; }
.stage-list { padding: 6px 4px; }
.stage-row { display: grid; grid-template-columns: 25px 1fr auto; min-height: 44px; align-items: center; color: #657087; }
.stage-row i { display: grid; width: 17px; height: 17px; place-items: center; border-radius: 50%; color: #95a0b2; font-style: normal; }
.stage-row b { color: #8992a3; font-size: 12px; font-weight: 500; }
.stage-row--done i { color: #fff; background: var(--aima-success); }
.stage-row--done b { color: var(--aima-success); }
.stage-row--current { color: #263043; font-weight: 600; }
.stage-row--current i { color: #fff; background: #2563eb; }
.stage-row--current b { color: #2563eb; }
.info-note { margin-top: 16px; padding: 12px; border: 1px solid #bcd5ff; border-radius: 6px; color: #2563eb; background: #f1f6ff; font-size: 12px; }
.error-card { padding: 15px; border: 1px solid #ffc7cc; border-radius: 7px; color: #b4232d; background: #fff5f6; }
.error-card p { margin-bottom: 0; }
.empty-error { padding: 50px 0; color: #8992a3; text-align: center; }
.drawer-footer { position: absolute; right: 0; bottom: 0; left: 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; padding: 14px 20px; border-top: 1px solid var(--aima-border); background: #fff; }
.drawer-footer button { height: 40px; border: 1px solid #d8dde6; border-radius: 6px; background: #fff; cursor: pointer; }
.drawer-footer .primary { border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); }
.drawer-footer button:disabled { color: #a3aab6; cursor: default; }
</style>
