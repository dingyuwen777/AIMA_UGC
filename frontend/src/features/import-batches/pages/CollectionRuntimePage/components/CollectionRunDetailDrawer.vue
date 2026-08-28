<script setup lang="ts">
import type { CollectionRunResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import {
  elapsed,
  formatDateTime,
  formatNumber,
  platformLabels,
  runtimeFailureMessage,
  runtimeStageLabel,
  runtimeStatusLabels,
  shortId,
} from '../../../format'

defineProps<{ modelValue: boolean; item: CollectionRunResponse | null }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  refresh: []
  copy: [value: string]
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="drawer-layer"
      @click.self="emit('update:modelValue', false)"
    >
      <aside
        class="drawer"
        role="dialog"
        aria-modal="true"
        aria-label="TikHub 运行详情"
      >
        <template v-if="item">
          <header>
            <strong>辅助补采运行详情</strong>
            <AimaButton
              variant="text"
              size="small"
              aria-label="关闭详情"
              @click="emit('update:modelValue', false)"
            >
              关闭
            </AimaButton>
          </header>

          <div class="drawer-body">
            <div class="title-row">
              <div><span>{{ item.mode === 'discovery' ? '独立发现新内容' : '基于已有批次补采' }}</span><h2>{{ item.keywords?.length ? item.keywords.join(' / ') : '批次内容补采' }}</h2></div>
              <b :class="`status status--${item.status}`">{{ runtimeStatusLabels[item.status] }}</b>
            </div>
            <section class="facts">
              <div><span>运行编号</span><strong>{{ shortId(item.run_id) }}</strong></div>
              <div><span>后台任务编号</span><strong>{{ shortId(item.job_id) }}</strong></div>
              <div><span>目标平台</span><strong>{{ item.platforms.map((platform) => platformLabels[platform]).join(' / ') }}</strong></div>
              <div><span>关联批次</span><strong>{{ item.import_batch_id ? shortId(item.import_batch_id) : '—' }}</strong></div>
              <div><span>尝试次数</span><strong>{{ item.attempt }} / {{ item.max_attempts }}</strong></div>
              <div><span>总耗时</span><strong>{{ elapsed(item.started_at, item.finished_at) }}</strong></div>
            </section>
            <section class="progress-panel">
              <div><strong>{{ runtimeStageLabel(item.stage) }}</strong><span>{{ item.progress }}%</span></div>
              <div class="track">
                <span :style="{ width: `${item.progress}%` }" />
              </div>
            </section>
            <h3>处理统计</h3>
            <section class="stats">
              <div><span>请求</span><strong>{{ formatNumber(item.stats.requested_count) }}</strong></div>
              <div><span>成功</span><strong>{{ formatNumber(item.stats.succeeded_count) }}</strong></div>
              <div class="stat-error"><span>失败</span><strong>{{ formatNumber(item.stats.failed_count) }}</strong></div>
              <div><span>内容</span><strong>{{ formatNumber(item.stats.content_count) }}</strong></div>
              <div><span>评论</span><strong>{{ formatNumber(item.stats.comment_count) }}</strong></div>
              <div><span>相关性过滤</span><strong>{{ formatNumber(item.stats.filtered_count) }}</strong></div>
            </section>
            <h3>执行范围状态</h3>
            <section class="scopes">
              <div
                v-for="scope in item.scopes"
                :key="scope.id"
              >
                <i :class="`dot dot--${scope.status}`" /><span>{{ platformLabels[scope.platform] }} · {{ runtimeStageLabel(scope.operation_group) }}<small
                  v-if="scope.status === 'failed' && scope.stop_reason"
                >{{ runtimeFailureMessage(scope.stop_reason) }}</small></span><b :class="`scope-state scope-state--${scope.status}`">{{ runtimeStatusLabels[scope.status] }} · {{ scope.progress }}%</b>
              </div>
            </section>
            <AimaFeedbackBanner
              v-if="item.error_summary"
              class="error-card"
              :tone="item.status === 'partial_success' ? 'warning' : 'error'"
              role="alert"
            >
              {{ item.error_code || 'collection_run_failed' }} · {{ runtimeFailureMessage(item.error_summary) }}
            </AimaFeedbackBanner>
            <AimaFeedbackBanner
              v-else-if="item.status === 'partial_success'"
              class="error-card"
              tone="warning"
            >
              部分执行范围未完成；错误摘要和停止原因以系统提供的安全错误信息为准。
            </AimaFeedbackBanner>
          </div>
          <footer>
            <span>创建于 {{ formatDateTime(item.created_at) }}</span>
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
.drawer { position: absolute; inset: 0 0 0 auto; display: grid; width: min(510px, 100vw); height: 100vh; grid-template-rows: 60px minmax(0, 1fr) 72px; overflow: hidden; border-left: 1px solid var(--aima-border); background: var(--aima-surface); box-shadow: -10px 0 30px rgb(23 32 51 / 12%); }
header { display: flex; align-items: center; justify-content: space-between; padding: 0 22px; border-bottom: 1px solid var(--aima-border); }
header strong { color: var(--aima-text); font-size: 17px; line-height: 24px; }
.drawer-body { min-height: 0; padding: 14px 22px 18px; overflow-x: hidden; overflow-y: auto; }
.title-row { display: flex; min-height: 50px; align-items: flex-start; justify-content: space-between; gap: 12px; }
.title-row span { color: var(--aima-text-disabled); font-size: 12px; line-height: 18px; }
.title-row h2 { max-width: 330px; margin: 2px 0 0; color: var(--aima-text); font-size: 18px; line-height: 26px; }
.status { flex: none; margin-top: 12px; padding: 5px 12px; border-radius: var(--aima-radius-control); color: #1677ff; background: #eef4ff; font-size: 11px; line-height: 18px; }
.status--succeeded { color: var(--aima-success); background: #f0fbf5; }
.status--failed { color: var(--aima-danger); background: #fff5f6; }
.status--partial_success { color: var(--aima-warning); background: #fff9e8; }
.facts { display: grid; grid-template-columns: 1fr 1fr; overflow: hidden; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); }
.facts > div { min-height: 68px; padding: 10px 11px; border-right: 1px solid var(--aima-border); border-bottom: 1px solid var(--aima-border); }
.facts > div:nth-child(2n) { border-right: 0; }
.facts > div:nth-last-child(-n + 2) { border-bottom: 0; }
.facts span, .facts strong { display: block; }
.facts span { color: var(--aima-text-disabled); font-size: 11px; line-height: 17px; }
.facts strong { overflow: hidden; margin-top: 5px; color: var(--aima-text); font-size: 12px; font-weight: 500; line-height: 20px; text-overflow: ellipsis; white-space: nowrap; }
.progress-panel { margin-top: 14px; padding: 11px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); }
.progress-panel > div:first-child { display: flex; justify-content: space-between; color: var(--aima-text); font-size: 12px; line-height: 18px; }
.progress-panel > div:first-child span { color: #1677ff; }
.track { height: 8px; margin-top: 12px; overflow: hidden; border-radius: 4px; background: #f8fafc; }
.track span { display: block; height: 100%; border-radius: inherit; background: #1677ff; }
h3 { margin: 18px 0 10px; color: var(--aima-text); font-size: 14px; line-height: 20px; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.stats div { min-height: 64px; padding: 8px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); }
.stats span, .stats strong { display: block; }
.stats span { color: var(--aima-text-disabled); font-size: 10px; line-height: 16px; }
.stats strong { margin-top: 4px; color: var(--aima-primary); font-size: 16px; line-height: 22px; }
.stats .stat-error strong { color: var(--aima-danger); }
.scopes { overflow: hidden; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); }
.scopes > div { display: grid; min-height: 42px; grid-template-columns: 10px minmax(0, 1fr) 120px; gap: 8px; align-items: center; padding: 0 12px; border-bottom: 1px solid var(--aima-border); color: var(--aima-text-secondary); font-size: 11px; }
.scopes > div:last-child { border-bottom: 0; }
.scopes small { display: block; overflow: hidden; margin-top: 2px; color: var(--aima-danger); text-overflow: ellipsis; white-space: nowrap; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--aima-text-disabled); }
.dot--running, .dot--queued { background: #1677ff; }
.dot--succeeded { background: var(--aima-success); }
.dot--failed { background: var(--aima-danger); }
.scope-state { justify-self: end; font-size: 11px; font-weight: 500; }
.scope-state--running, .scope-state--queued { color: #1677ff; }
.scope-state--succeeded { color: var(--aima-success); }
.scope-state--failed { color: var(--aima-danger); }
.error-card { margin-top: 32px; }
footer { display: flex; align-items: center; justify-content: space-between; padding: 0 22px; border-top: 1px solid var(--aima-border); background: var(--aima-surface); color: var(--aima-text-disabled); font-size: 11px; }
</style>
