<script setup lang="ts">
import { computed } from 'vue'
import type { CollectionRunResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaDrawer from '../../../../../shared/ui/AimaDrawer.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import {
  elapsed,
  formatDateTime,
  formatNumber,
  platformLabels,
  runtimeFailureMessage,
  runtimeStageLabel,
  runtimeStatusLabels,
} from '../../../format'

const props = defineProps<{ modelValue: boolean; item: CollectionRunResponse | null }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  refresh: []
  copy: [value: string]
  viewResults: [runId: string]
}>()

const identityStatusLabels = {
  resolving: '解析中',
  resolved: '已确认',
  unavailable: '不可获取',
  ambiguous: '归属不明确',
  conflict: '身份冲突',
} as const
const commentStageLabels = {
  roots: '一级评论抓取中',
  replies: '回复抓取中',
  finished: '抓取结束',
} as const

const coverageByPlatform = computed(() => (props.item?.platforms ?? []).map((platform) => {
  const scopes = props.item?.scopes.filter((scope) => scope.platform === platform) ?? []
  const blocked = (scope: typeof scopes[number]) => ['identity_unavailable', 'exact_resolution_unavailable', 'identity_conflict'].includes(scope.stop_reason ?? '')
  return {
    platform,
    complete: scopes.filter((scope) => scope.comment_coverage === 'complete' && scope.status === 'succeeded').length,
    partial: scopes.filter((scope) => scope.comment_coverage === 'partial' || scope.status === 'partial_success').length,
    unavailable: scopes.filter((scope) => scope.comment_coverage === 'unavailable' || blocked(scope)).length,
    failed: scopes.filter((scope) => scope.status === 'failed' && !blocked(scope)).length,
    pending: scopes.filter((scope) => scope.status === 'queued' || scope.status === 'running').length,
  }
}))
</script>

<template>
  <AimaDrawer
    :model-value="modelValue"
    label="辅助补采运行详情"
    width="510px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <header class="drawer-header">
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
    </template>

    <div
      v-if="item"
      class="drawer-content"
    >
      <div class="title-row">
        <div>
          <span>{{ item.mode === 'discovery' ? '独立发现新内容' : '基于已有批次补采' }}</span><h2>{{ item.keywords?.length ? item.keywords.join(' / ') : '批次内容补采' }}</h2>
        </div>
        <b :class="`status status--${item.status}`">{{ runtimeStatusLabels[item.status] }}</b>
      </div>
      <section class="facts">
        <div><span>补采方式</span><strong>{{ item.mode === 'discovery' ? '独立发现' : '基于历史批次' }}</strong></div>
        <div><span>目标平台</span><strong>{{ item.platforms.map((platform) => platformLabels[platform]).join(' / ') }}</strong></div>
        <div><span>来源任务</span><strong>{{ item.mode === 'discovery' ? (item.keywords?.join(' / ') || '关键词发现') : '已关联导入来源' }}</strong></div>
        <div><span>总耗时</span><strong>{{ elapsed(item.started_at, item.finished_at) }}</strong></div>
      </section>
      <section class="progress-panel">
        <div><strong>{{ runtimeStageLabel(item.stage) }}</strong><span>{{ item.progress }}%</span></div>
        <div class="track">
          <span :style="{ width: `${item.progress}%` }" />
        </div>
        <small v-if="item.status === 'queued' || item.status === 'running'">
          执行尝试 {{ item.attempt }} / {{ item.max_attempts }}；短暂故障由后台自动重试。
        </small>
      </section>
      <h3>处理统计</h3>
      <section class="stats">
        <div><span>请求</span><strong>{{ formatNumber(item.stats.requested_count) }}</strong></div>
        <div><span>成功</span><strong>{{ formatNumber(item.stats.succeeded_count) }}</strong></div>
        <div class="stat-error">
          <span>失败</span><strong>{{ formatNumber(item.stats.failed_count) }}</strong>
        </div>
        <div><span>内容</span><strong>{{ formatNumber(item.stats.content_count) }}</strong></div>
        <div><span>评论</span><strong>{{ formatNumber(item.stats.comment_count) }}</strong></div>
        <div><span>一级评论</span><strong>{{ formatNumber(item.stats.root_comment_count) }}</strong></div>
        <div><span>回复</span><strong>{{ formatNumber(item.stats.reply_count) }}</strong></div>
        <div><span>相关性过滤</span><strong>{{ formatNumber(item.stats.filtered_count) }}</strong></div>
      </section>
      <template v-if="item.mode === 'batch_supplement'">
        <h3>平台评论覆盖</h3>
        <section
          class="coverage-summary"
          aria-label="平台评论覆盖"
        >
          <div
            v-for="coverage in coverageByPlatform"
            :key="coverage.platform"
          >
            <strong>{{ platformLabels[coverage.platform] }}</strong>
            <span>完整 {{ coverage.complete }} · 部分 {{ coverage.partial }} · 不可用 {{ coverage.unavailable }} · 失败 {{ coverage.failed }} · 待处理 {{ coverage.pending }}</span>
          </div>
        </section>
      </template>
      <h3>执行范围状态</h3>
      <section class="scopes">
        <div
          v-for="scope in item.scopes"
          :key="scope.id"
        >
          <i :class="`dot dot--${scope.status}`" /><span>{{ platformLabels[scope.platform] }} · {{ runtimeStageLabel(scope.operation_group) }}<small v-if="scope.identity_status">目标身份：{{ identityStatusLabels[scope.identity_status] }}</small><small v-if="scope.comment_stage">{{ commentStageLabels[scope.comment_stage] }}</small><small v-if="scope.comment_coverage">一级评论 {{ scope.stats.root_comment_count }} · 回复 {{ scope.stats.reply_count }} · 评论覆盖：{{ scope.comment_coverage === 'complete' ? '完整' : scope.comment_coverage === 'partial' ? '部分' : scope.comment_coverage === 'unavailable' ? '不可用' : '未请求' }}</small><small
            v-if="scope.status === 'failed' && scope.stop_reason"
          >{{ runtimeFailureMessage(scope.stop_reason) }}</small></span><b :class="`scope-state scope-state--${scope.status}`">{{ runtimeStatusLabels[scope.status] }} · {{ scope.progress }}%</b>
        </div>
      </section>
      <AimaFeedbackBanner
        v-if="item.error_summary || item.error_code"
        class="error-card"
        :tone="item.status === 'partial_success' ? 'warning' : 'error'"
        role="alert"
      >
        {{ runtimeFailureMessage(item.error_code ?? item.error_summary) }}
      </AimaFeedbackBanner>
      <AimaFeedbackBanner
        v-else-if="item.status === 'partial_success'"
        class="error-card"
        tone="warning"
      >
        部分内容未完成；请查看平台停止原因，修复后从原来源新建补采任务。
      </AimaFeedbackBanner>

      <details class="technical-details">
        <summary>技术详情</summary>
        <div class="technical-grid">
          <div>
            <span>运行 ID</span><code>{{ item.run_id }}</code><button
              type="button"
              @click="emit('copy', item.run_id)"
            >
              复制
            </button>
          </div>
          <div>
            <span>后台任务 ID</span><code>{{ item.job_id }}</code><button
              type="button"
              @click="emit('copy', item.job_id)"
            >
              复制
            </button>
          </div>
          <div v-if="item.import_batch_id">
            <span>关联导入 ID</span><code>{{ item.import_batch_id }}</code><button
              type="button"
              @click="emit('copy', item.import_batch_id)"
            >
              复制
            </button>
          </div>
          <div><span>执行尝试</span><code>{{ item.attempt }} / {{ item.max_attempts }}</code></div>
          <div v-if="item.error_code">
            <span>错误码</span><code>{{ item.error_code }}</code>
          </div>
          <div v-if="item.error_summary">
            <span>错误摘要</span><code>{{ item.error_summary }}</code>
          </div>
        </div>
        <div
          v-if="item.scopes.some((scope) => scope.stop_reason)"
          class="technical-scopes"
        >
          <strong>平台停止原因</strong>
          <p
            v-for="scope in item.scopes.filter((value) => value.stop_reason)"
            :key="scope.id"
          >
            {{ platformLabels[scope.platform] }}：<code>{{ scope.stop_reason }}</code>
          </p>
        </div>
      </details>
    </div>

    <template #footer>
      <footer
        v-if="item"
        class="drawer-footer"
      >
        <span>创建于 {{ formatDateTime(item.created_at) }}</span>
        <AimaButton
          v-if="item.mode === 'batch_supplement'"
          variant="secondary"
          @click="emit('viewResults', item.run_id)"
        >
          查看补采结果
        </AimaButton>
        <AimaButton
          variant="primary"
          @click="emit('refresh')"
        >
          刷新详情
        </AimaButton>
      </footer>
    </template>
  </AimaDrawer>
</template>

<style scoped>
.drawer-header { display: flex; height: 60px; align-items: center; justify-content: space-between; padding: 0 22px; border-bottom: 1px solid var(--aima-border); background: var(--aima-surface); }
.drawer-header strong { color: var(--aima-text); font-size: 17px; font-weight: 700; line-height: 24px; }
.drawer-content { min-height: 711px; padding: 14px 22px 43px; }
.title-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.title-row > div { min-width: 0; }
.title-row span { color: var(--aima-color-text-tertiary); font-size: 12px; line-height: 18px; }
.title-row h2 { max-width: 330px; margin: 4px 0 0; overflow: hidden; color: var(--aima-text); font-size: 18px; font-weight: 700; line-height: 26px; text-overflow: ellipsis; white-space: nowrap; }
.status { flex: none; padding: 4px 10px; border-radius: 6px; color: var(--aima-color-info); background: var(--aima-color-bg-subtle); font-size: 11px; font-weight: 500; line-height: 18px; }
.status--succeeded { color: var(--aima-success); }
.status--failed { color: var(--aima-danger); background: var(--aima-color-error-bg); }
.status--partial_success { color: var(--aima-warning); }
.facts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; padding: 16px; border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.facts > div { min-width: 0; padding: 10px 12px; border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.facts span, .facts strong { display: block; }
.facts span { color: var(--aima-color-text-tertiary); font-size: 11px; line-height: 16px; }
.facts strong { overflow: hidden; margin-top: 8px; color: var(--aima-text); font-size: 16px; font-weight: 700; line-height: 22px; text-overflow: ellipsis; white-space: nowrap; }
.progress-panel { margin-top: 16px; padding: 12px; border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.progress-panel > div:first-child { display: flex; justify-content: space-between; color: var(--aima-text); font-size: 12px; font-weight: 500; line-height: 18px; }
.progress-panel > div:first-child span { color: var(--aima-color-info); }
.track { height: 8px; margin-top: 12px; overflow: hidden; border-radius: 4px; background: var(--aima-color-bg-subtle); }
.track span { display: block; height: 100%; border-radius: inherit; background: var(--aima-color-info); }
h3 { margin: 16px 0 10px; color: var(--aima-text); font-size: 14px; font-weight: 500; line-height: 20px; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.stats div { min-height: 64px; padding: 12px; border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.stats span, .stats strong { display: block; }
.stats span { color: var(--aima-color-text-tertiary); font-size: 10px; line-height: 16px; }
.stats strong { margin-top: 4px; color: var(--aima-primary); font-size: 16px; font-weight: 700; line-height: 22px; }
.stats .stat-error strong { color: var(--aima-danger); }
.coverage-summary { overflow: hidden; border-radius: 7px; background: var(--aima-surface); }
.coverage-summary > div { display: flex; justify-content: space-between; gap: 8px; padding: 10px 12px; border-bottom: 1px solid var(--aima-border); font-size: 11px; }
.coverage-summary > div:last-child { border-bottom: 0; }
.coverage-summary strong { color: var(--aima-text); }
.coverage-summary span { color: var(--aima-text-secondary); text-align: right; }
.scopes { overflow: hidden; border-radius: 7px; background: var(--aima-surface); }
.scopes > div { display: grid; min-height: 42px; grid-template-columns: 8px minmax(0, 1fr) 120px; gap: 12px; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--aima-border); color: var(--aima-text-secondary); font-size: 11px; }
.scopes > div:last-child { border-bottom: 0; }
.scopes small { display: block; overflow: hidden; margin-top: 2px; color: var(--aima-danger); text-overflow: ellipsis; white-space: nowrap; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--aima-text-disabled); }
.dot--running, .dot--queued { background: var(--aima-color-info); }
.dot--succeeded { background: var(--aima-success); }
.dot--failed { background: var(--aima-danger); }
.scope-state { justify-self: end; font-size: 11px; font-weight: 500; }
.scope-state--running, .scope-state--queued { color: var(--aima-color-info); }
.scope-state--succeeded { color: var(--aima-success); }
.scope-state--failed { color: var(--aima-danger); }
.error-card { margin-top: 16px; }
.technical-details { margin-top: 22px; border-top: 1px solid var(--aima-border); padding-top: 14px; color: var(--aima-text-muted); font-size: 11px; }
.technical-details summary { width: max-content; color: var(--aima-text-muted); cursor: pointer; font-size: 12px; font-weight: 500; }
.technical-grid { display: grid; gap: 8px; margin-top: 12px; }
.technical-grid > div { display: grid; grid-template-columns: 92px minmax(0, 1fr) auto; align-items: center; gap: 8px; }
.technical-grid code, .technical-scopes code { overflow-wrap: anywhere; color: var(--aima-text-secondary); font-size: 10px; }
.technical-grid button { border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 10px; }
.technical-scopes { margin-top: 12px; }
.technical-scopes p { margin: 6px 0 0; }
.drawer-footer { display: flex; height: 72px; align-items: center; justify-content: space-between; padding: 0 22px; border-top: 1px solid var(--aima-border); background: var(--aima-surface); color: var(--aima-color-text-tertiary); font-size: 11px; }
.drawer-footer :deep(.aima-button.is-primary) { min-width: 104px; }
</style>
