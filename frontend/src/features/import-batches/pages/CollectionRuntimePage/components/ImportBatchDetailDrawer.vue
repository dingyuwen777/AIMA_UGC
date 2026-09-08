<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { ImportBatchResponse, ImportStage } from '../../../../../generated/api/client'
import { importSourceRetention } from '../../../../../shared/artifactRetention'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { elapsed, formatDateTime, formatNumber, stageLabels, statusLabels } from '../../../format'

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
    ? '任务已取消，系统无法准确还原取消前最后完成的处理步骤。'
    : '任务已失败，系统无法准确还原失败前最后完成的处理步骤。',
)
const sourceRetention = computed(() =>
  importSourceRetention(props.item?.finished_at ?? props.item?.job.finished_at),
)
const sourceRetentionText = computed(() => {
  if (sourceRetention.value.expiresAt === null) return '源 Excel 会在任务结束后继续保留 7 天，处理和重试期间不会提前清理。'
  if (sourceRetention.value.expired) return '源 Excel 已超过 7 天保留期并进入自动清理；导入记录、已入库数据和来源信息继续保留。'
  return `源 Excel 保留至 ${formatDateTime(sourceRetention.value.expiresAt)}；到期后只清理文件本身。`
})

/** 业务主视图优先显示可理解的问题说明，不直接暴露未知机器错误码。 */
function importFailureMessage(summary: string | null | undefined): string {
  const text = summary?.trim() ?? ''
  if (text && /[\u3400-\u9fff]/u.test(text)) return text
  return '数据导入遇到问题，请重试；如持续失败，请联系管理员查看技术详情。'
}
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
        aria-label="数据导入详情"
      >
        <template v-if="item">
          <header class="drawer-header">
            <strong>数据导入详情</strong>
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
              v-for="tab in [{ name: 'overview', label: '导入概览' }, { name: 'stages', label: '处理阶段' }, { name: 'status', label: '运行状态' }, { name: 'errors', label: '问题记录' }]"
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
                <h2>{{ item.source_filename || '数据导入' }}</h2><span :class="`status-tag status-tag--${item.status}`">{{ statusLabels[item.status] }}</span>
              </div>
              <div class="fact-grid">
                <div><span>来源文件</span><strong>{{ item.source_filename || '—' }}</strong></div>
                <div><span>创建时间</span><strong>{{ formatDateTime(item.created_at) }}</strong></div>
                <div><span>开始时间</span><strong>{{ formatDateTime(item.started_at) }}</strong></div>
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
              <h3>处理结果</h3>
              <div class="stat-grid">
                <div><span>读取</span><strong>{{ formatNumber(item.stats.rows_seen) }}</strong></div>
                <div><span>相关</span><strong>{{ formatNumber(item.stats.rows_matched) }}</strong></div>
                <div><span>已过滤</span><strong>{{ formatNumber(item.stats.rows_filtered_out) }}</strong></div>
                <div><span>重复</span><strong>{{ formatNumber(item.stats.duplicates_removed) }}</strong></div>
                <div><span>已入库</span><strong>{{ formatNumber(item.stats.rows_ingested) }}</strong></div>
                <div><span>未导入</span><strong>{{ formatNumber(item.stats.rows_rejected) }}</strong></div>
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
                  <i aria-hidden="true" /><span>接收文件</span><b>完成</b>
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
                {{ terminalStageMessage }} 可到“问题记录”查看当前可用的失败信息。
              </AimaFeedbackBanner>
            </section>

            <section
              v-else-if="activeTab === 'status'"
              class="tab-content"
            >
              <h3>运行状态</h3>
              <div class="fact-grid fact-grid--single">
                <div><span>当前状态</span><strong>{{ statusLabels[item.job.status] }}</strong></div>
                <div><span>开始时间</span><strong>{{ formatDateTime(item.job.started_at) }}</strong></div>
                <div><span>结束时间</span><strong>{{ formatDateTime(item.job.finished_at) }}</strong></div>
                <div><span>当前进度</span><strong>{{ item.job.progress }}%</strong></div>
              </div>
              <AimaFeedbackBanner
                class="info-note"
                tone="info"
              >
                详情会定期自动刷新；关闭页面后导入任务仍会继续在后台执行。
              </AimaFeedbackBanner>
              <details class="technical-details">
                <summary>技术详情</summary>
                <div class="technical-grid">
                  <div>
                    <span>导入 ID</span><code>{{ item.id }}</code><button
                      type="button"
                      @click="emit('copy', item.id)"
                    >
                      复制
                    </button>
                  </div>
                  <div>
                    <span>后台任务 ID</span><code>{{ item.job.id }}</code><button
                      type="button"
                      @click="emit('copy', item.job.id)"
                    >
                      复制
                    </button>
                  </div>
                  <div><span>任务类型</span><code>{{ item.job.job_type }}</code></div>
                  <div><span>执行尝试</span><code>{{ item.job.attempt }} / {{ item.job.max_attempts }}</code></div>
                </div>
              </details>
            </section>

            <section
              v-else
              class="tab-content"
            >
              <h3>问题记录</h3>
              <AimaFeedbackBanner
                v-if="item.error_summary || item.job.error_code"
                tone="error"
                role="alert"
              >
                {{ importFailureMessage(item.error_summary) }}
              </AimaFeedbackBanner>
              <div
                v-else
                class="empty-error"
              >
                当前没有问题记录。
              </div>
              <details
                v-if="item.error_summary || item.job.error_code"
                class="technical-details"
              >
                <summary>技术详情</summary>
                <div class="technical-grid">
                  <div v-if="item.job.error_code">
                    <span>错误码</span><code>{{ item.job.error_code }}</code>
                  </div>
                  <div v-if="item.error_summary">
                    <span>错误摘要</span><code>{{ item.error_summary }}</code>
                  </div>
                </div>
              </details>
            </section>
          </div>

          <footer class="drawer-footer">
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
.drawer-layer { position: fixed; inset: 0; z-index: 100; background: rgb(17 22 37 / 50%); }
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
.technical-details { margin-top: 20px; border-top: 1px solid var(--aima-border); padding-top: 12px; color: var(--aima-text-muted); font-size: 11px; }
.technical-details summary { width: max-content; cursor: pointer; font-size: 12px; font-weight: 500; }
.technical-grid { display: grid; gap: 8px; margin-top: 12px; }
.technical-grid > div { display: grid; grid-template-columns: 82px minmax(0, 1fr) auto; align-items: center; gap: 8px; }
.technical-grid code { overflow-wrap: anywhere; color: var(--aima-text-secondary); font-size: 10px; }
.technical-grid button { border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 10px; }
.drawer-footer { display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding: 0 20px; border-top: 1px solid var(--aima-border); background: var(--aima-surface); }
</style>
