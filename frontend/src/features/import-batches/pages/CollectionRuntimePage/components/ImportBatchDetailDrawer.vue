<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { ImportBatchResponse, ImportStage } from '../../../../../generated/api/client'
import { importSourceRetention } from '../../../../../shared/artifactRetention'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
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
const showStageTimeline = computed(() =>
  props.item !== null && !['failed', 'cancelled'].includes(props.item.status),
)
const stageRows = computed(() => {
  const current = props.item?.stage ?? 'queued'
  const currentIndex = stageOrder.indexOf(current)
  return stageOrder.map((stage, index) => ({
    stage,
    state:
      current === 'succeeded'
        ? 'done'
        : index < currentIndex
          ? 'done'
          : index === currentIndex
            ? 'current'
            : 'pending',
  }))
})
const terminalStageMessage = computed(() =>
  props.item?.status === 'cancelled'
    ? '任务已取消。当前公开 Contract 不保存足以可靠重建“取消前最后完成阶段”的历史，因此这里不把未知阶段伪装成等待中。'
    : '任务已失败。当前公开 Contract 不保存足以可靠重建“失败前最后完成阶段”的历史，因此这里不把未知阶段伪装成等待中。',
)
const sourceRetention = computed(() =>
  importSourceRetention(props.item?.finished_at ?? props.item?.job.finished_at),
)
const sourceRetentionText = computed(() => {
  if (sourceRetention.value.expiresAt === null) return '源 Excel 会在任务进入终态后继续保留 7 天，处理和重试期间不会提前清理。'
  if (sourceRetention.value.expired) return '源 Excel 已超过 7 天保留期并进入自动清理；批次、入库数据和来源元数据继续保留。'
  return `源 Excel 保留至 ${formatDateTime(sourceRetention.value.expiresAt)}；到期后只清理文件字节。`
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
            <strong>批次详情</strong>
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
            aria-label="详情标签页"
          >
            <button
              v-for="tab in [{ name: 'overview', label: '运行概览' }, { name: 'stages', label: '处理阶段' }, { name: 'job', label: '后台任务状态' }, { name: 'errors', label: '错误记录' }]"
              :key="tab.name"
              type="button"
              :class="{ active: activeTab === tab.name }"
              @click="activeTab = tab.name"
            >
              {{ tab.label }}
            </button>
          </nav>

          <div class="drawer-body">
            <section
              v-if="activeTab === 'overview'"
              class="tab-content"
            >
              <div class="detail-title">
                <h2>{{ item.source_filename || '数据导入批次' }}</h2><span :class="`status-tag status-tag--${item.status}`">{{ statusLabels[item.status] }}</span>
              </div>
              <div class="fact-grid">
                <div><span>批次编号</span><strong>{{ shortId(item.id) }}</strong></div>
                <div><span>后台任务编号</span><strong>{{ shortId(item.job.id) }}</strong></div>
                <div><span>来源文件</span><strong>{{ item.source_filename || '—' }}</strong></div>
                <div><span>创建时间</span><strong>{{ formatDateTime(item.created_at) }}</strong></div>
                <div><span>尝试次数</span><strong>{{ item.job.attempt }} / {{ item.job.max_attempts }}</strong></div>
                <div><span>总耗时</span><strong>{{ elapsed(item.started_at, item.finished_at) }}</strong></div>
              </div>
              <AimaFeedbackBanner
                class="retention-note"
                :tone="sourceRetention.expired ? 'error' : 'warning'"
                :role="sourceRetention.expired ? 'alert' : 'status'"
              >
                {{ sourceRetentionText }}
              </AimaFeedbackBanner>
              <div class="progress-panel">
                <div><strong>总体进度</strong><span>{{ item.job.progress }}%</span></div>
                <div class="detail-progress">
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
              <div
                v-if="showStageTimeline"
                class="stage-list"
              >
                <div class="stage-row stage-row--done">
                  <i aria-hidden="true" /><span>上传与 Artifact</span><b>成功</b>
                </div>
                <div
                  v-for="row in stageRows"
                  :key="row.stage"
                  class="stage-row"
                  :class="`stage-row--${row.state}`"
                >
                  <i aria-hidden="true" /><span>{{ stageLabels[row.stage] }}</span><b>{{ row.state === 'done' ? '完成' : row.state === 'current' ? '进行中' : '等待中' }}</b>
                </div>
              </div>
              <AimaFeedbackBanner
                v-else
                :tone="item.status === 'cancelled' ? 'warning' : 'error'"
                role="alert"
              >
                {{ terminalStageMessage }} 请切换到“后台任务状态”和“错误记录”查看可审计的终态事实。
              </AimaFeedbackBanner>
            </section>

            <section
              v-else-if="activeTab === 'job'"
              class="tab-content"
            >
              <h3>持久化导入后台任务</h3>
              <div class="fact-grid fact-grid--single">
                <div><span>任务类型</span><strong>{{ item.job.job_type }}</strong></div>
                <div><span>状态</span><strong>{{ statusLabels[item.job.status] }}</strong></div>
                <div><span>开始时间</span><strong>{{ formatDateTime(item.job.started_at) }}</strong></div>
                <div><span>结束时间</span><strong>{{ formatDateTime(item.job.finished_at) }}</strong></div>
              </div>
              <AimaFeedbackBanner
                class="info-note"
                tone="info"
              >
                详情每 5 秒自动刷新；关闭页面后后台任务仍由 Worker 持续执行。
              </AimaFeedbackBanner>
            </section>

            <section
              v-else
              class="tab-content"
            >
              <h3>安全错误摘要</h3>
              <AimaFeedbackBanner
                v-if="item.error_summary"
                tone="error"
                role="alert"
              >
                {{ item.job.error_code || 'import_failed' }} · {{ item.error_summary }}
              </AimaFeedbackBanner>
              <div
                v-else
                class="empty-error"
              >
                当前没有错误记录。
              </div>
            </section>
          </div>

          <footer class="drawer-footer">
            <AimaButton
              variant="text"
              size="small"
              @click="emit('copy', item.id)"
            >
              复制批次编号
            </AimaButton>
            <AimaButton
              variant="secondary"
              size="small"
              :disabled="item.stats.rows_ingested === 0"
              @click="emit('viewContents', item.id)"
            >
              查看入库内容
            </AimaButton>
            <AimaButton
              variant="primary"
              @click="emit('refresh')"
            >
              刷新详情
            </AimaButton>
          </footer>
        </template>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer-layer { position: fixed; inset: 0; z-index: 100; background: rgb(17 22 37 / 94%); }
.drawer { position: absolute; inset: 0 0 0 auto; display: grid; width: min(450px, 100vw); height: 100vh; grid-template-rows: 60px 44px minmax(0, 1fr) 72px; overflow: hidden; border-left: 1px solid var(--aima-border); background: var(--aima-surface); box-shadow: -10px 0 30px rgb(23 32 51 / 12%); }
.drawer-header { display: flex; align-items: center; justify-content: space-between; padding: 0 20px; border-bottom: 1px solid var(--aima-border); }
.drawer-header strong { color: var(--aima-text); font-size: 17px; line-height: 24px; }
.detail-tabs { display: grid; grid-template-columns: repeat(4, 1fr); padding: 0 10px; border-bottom: 1px solid var(--aima-border); }
.detail-tabs button { height: 44px; padding: 0 4px; border: 0; border-bottom: 2px solid transparent; color: var(--aima-text-muted); background: transparent; cursor: pointer; font-size: 13px; }
.detail-tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 500; }
.drawer-body { min-height: 0; padding: 8px 20px 16px; overflow-x: hidden; overflow-y: auto; }
.detail-title { display: flex; min-height: 42px; align-items: center; justify-content: space-between; gap: 10px; }
.detail-title h2 { min-width: 0; margin: 0; overflow: hidden; color: var(--aima-text); font-size: 18px; line-height: 26px; text-overflow: ellipsis; white-space: nowrap; }
.status-tag { flex: none; padding: 5px 12px; border-radius: var(--aima-radius-control); color: #1677ff; background: #eef4ff; font-size: 12px; white-space: nowrap; }
.status-tag--succeeded { color: var(--aima-success); background: #f0fbf5; }
.status-tag--failed { color: var(--aima-danger); background: #fff5f6; }
.status-tag--cancelled { color: var(--aima-text-muted); background: #f1f3f6; }
.fact-grid { display: grid; grid-template-columns: 1fr 1fr; overflow: hidden; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); }
.fact-grid > div { min-height: 68px; padding: 10px 11px; border-right: 1px solid var(--aima-border); border-bottom: 1px solid var(--aima-border); }
.fact-grid > div:nth-child(2n) { border-right: 0; }
.fact-grid > div:nth-last-child(-n + 2) { border-bottom: 0; }
.fact-grid span, .fact-grid strong { display: block; }
.fact-grid span { color: var(--aima-text-disabled); font-size: 11px; line-height: 17px; }
.fact-grid strong { overflow: hidden; margin-top: 5px; color: var(--aima-text); font-size: 12px; font-weight: 500; line-height: 20px; text-overflow: ellipsis; white-space: nowrap; }
.fact-grid--single { grid-template-columns: 1fr; }
.fact-grid--single > div { border-right: 0; }
.fact-grid--single > div:nth-last-child(-n + 2) { border-bottom: 1px solid var(--aima-border); }
.fact-grid--single > div:last-child { border-bottom: 0; }
.retention-note { margin-top: 20px; }
.progress-panel { margin-top: 20px; padding: 11px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); }
.progress-panel > div:first-child { display: flex; justify-content: space-between; color: var(--aima-text); font-size: 12px; line-height: 18px; }
.progress-panel > div:first-child span { color: var(--aima-primary); }
.detail-progress { height: 8px; margin-top: 12px; overflow: hidden; border-radius: 4px; background: #f8fafc; }
.detail-progress span { display: block; height: 100%; border-radius: inherit; background: var(--aima-primary); }
h3 { margin: 20px 0 10px; color: var(--aima-text); font-size: 14px; line-height: 20px; }
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.stat-grid div { min-height: 64px; padding: 8px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); }
.stat-grid span, .stat-grid strong { display: block; }
.stat-grid span { color: var(--aima-text-disabled); font-size: 10px; line-height: 16px; }
.stat-grid strong { margin-top: 4px; color: var(--aima-primary); font-size: 16px; line-height: 22px; }
.stage-list { padding-top: 4px; }
.stage-row { display: grid; min-height: 48px; grid-template-columns: 24px 1fr auto; align-items: center; color: var(--aima-text-muted); }
.stage-row i { width: 10px; height: 10px; border: 2px solid var(--aima-border-strong); border-radius: 50%; }
.stage-row b { color: var(--aima-text-disabled); font-size: 12px; font-weight: 500; }
.stage-row--done i { border-color: var(--aima-success); background: var(--aima-success); }
.stage-row--done b { color: var(--aima-success); }
.stage-row--current { color: var(--aima-text); font-weight: 500; }
.stage-row--current i { border-color: #1677ff; background: #1677ff; }
.stage-row--current b { color: #1677ff; }
.info-note { margin-top: 20px; }
.empty-error { padding: 54px 0; color: var(--aima-text-muted); text-align: center; font-size: 12px; }
.drawer-footer { display: flex; align-items: center; gap: 10px; padding: 0 20px; border-top: 1px solid var(--aima-border); background: var(--aima-surface); }
.drawer-footer :deep(.aima-button:first-child) { margin-right: auto; }
</style>
