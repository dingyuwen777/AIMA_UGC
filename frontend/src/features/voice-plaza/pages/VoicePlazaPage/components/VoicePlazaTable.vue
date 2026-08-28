<script setup lang="ts">
import type {
  ContentLabelPairResponse,
  ContentListItemResponse,
} from '../../../../../generated/api/client'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import {
  contentSummary,
  formatDateTime,
  formatNumber,
  labelPairText,
  platformLabel,
} from '../../../format'
import {
  relevanceBadgeLabel,
  relevanceReviewActionLabel,
  relevanceReviewDecision,
  type RelevanceReviewDecision,
} from '../../../relevanceReview'

const props = defineProps<{
  items: ContentListItemResponse[]
  loading: boolean
  error?: string | null
  selectedIds: string[]
  reviewing: boolean
}>()
const emit = defineEmits<{
  detail: [contentId: string]
  toggle: [contentId: string]
  toggleAll: []
  review: [contentId: string, decision: RelevanceReviewDecision]
}>()

/** 将情感映射为表格中的稳定语义样式，不改变后端机器值。 */
function sentimentClass(sentiment?: string | null): string {
  if (sentiment === '正面') return 'status-badge status-badge--positive'
  if (sentiment === '负面') return 'status-badge status-badge--negative'
  return 'status-badge status-badge--neutral'
}

/** 读取当前内容完整的有序 AI 标签，不在表格层重建 Taxonomy。 */
function labels(item: ContentListItemResponse): ContentLabelPairResponse[] {
  return item.analysis.labels ?? []
}

/** 保留 AI 原判或人工复核来源文案，确保相关性来源可审计。 */
function badge(item: ContentListItemResponse): string | null {
  return relevanceBadgeLabel(item)
}

/** 优先展示已有相关性来源文案，否则展示当前业务有效相关性。 */
function relevanceText(item: ContentListItemResponse): string | null {
  const sourceBadge = badge(item)
  if (sourceBadge) return sourceBadge
  const effective = item.effective_relevance ?? item.analysis.relevance
  if (effective === 'relevant') return '相关'
  if (effective === 'irrelevant') return '不相关'
  return null
}

/** 为当前业务有效相关性选择视觉强调，不改变 review 决策语义。 */
function relevanceClass(item: ContentListItemResponse): string {
  const effective = item.effective_relevance ?? item.analysis.relevance
  return effective === 'relevant'
    ? 'status-badge status-badge--positive'
    : 'status-badge status-badge--neutral'
}

/** 组合 AI 当前性与人工覆盖来源，避免只展示情感而丢失状态。 */
function analysisMeta(item: ContentListItemResponse): string {
  const reviewBadge = badge(item)
  if (item.analysis.status === 'stale') {
    return reviewBadge ? `AI stale · ${reviewBadge}` : 'AI stale · 需重新打标'
  }
  if (item.analysis.status !== 'completed') {
    return reviewBadge ? `AI 未完成 · ${reviewBadge}` : 'AI 未完成'
  }
  return reviewBadge ? `AI 已完成 · ${reviewBadge}` : 'AI 已完成 · 人工未覆盖'
}

/** 返回当前行可执行的人工相关性复核决策。 */
function reviewDecision(item: ContentListItemResponse): RelevanceReviewDecision | null {
  return relevanceReviewDecision(item)
}

/** 为复核动作选择局部视觉语义，业务资格仍由 relevanceReviewDecision 唯一决定。 */
function reviewClass(item: ContentListItemResponse): string {
  const decision = reviewDecision(item)
  if (decision === 'irrelevant') return 'review-button review-button--irrelevant'
  if (decision === 'inherit_ai') return 'review-button review-button--undo'
  return 'review-button review-button--relevant'
}

/** 发出单条人工复核事件，不在表格组件内执行 API 调用。 */
function runReview(item: ContentListItemResponse): void {
  const decision = reviewDecision(item)
  if (decision) emit('review', item.id, decision)
}

/** 将北京时间格式拆成日期和时间两行，匹配紧凑表格布局。 */
function dateTimeParts(value: string | null | undefined): [string, string] {
  const formatted = formatDateTime(value)
  if (formatted === '—') return ['—', '']
  const [date, ...time] = formatted.split(/\s+/)
  return [date ?? formatted, time.join(' ')]
}
</script>

<template>
  <section
    class="content-list"
    aria-label="声音广场内容列表"
  >
    <div class="table-head">
      <label class="check"><input
        type="checkbox"
        :checked="items.length > 0 && items.every((item) => selectedIds.includes(item.id))"
        aria-label="选择当前已加载内容"
        @change="$emit('toggleAll')"
      ></label>
      <span>标题内容</span><span>AI 情感 / 标签</span><span>互动</span><span>平台 / 作者</span><span>发布时间</span><span>操作</span>
    </div>

    <div
      v-if="loading && items.length === 0"
      class="table-state table-state--loading"
      role="status"
    >
      <strong>正在加载声音记录…</strong>
      <span>正在获取内容列表、AI 状态与运行记录</span>
      <div class="skeleton skeleton--long" /><div class="skeleton skeleton--medium" /><div class="skeleton skeleton--short" />
    </div>
    <div
      v-else-if="error && items.length === 0"
      class="table-state table-state--error"
      role="alert"
    >
      <strong>暂时无法加载声音记录</strong>
      <span>检查网络或服务状态后点击“刷新数据”重试。</span>
    </div>
    <div
      v-else-if="items.length === 0"
      class="table-state table-state--empty"
    >
      <span class="empty-icon"><AimaIcon
        name="voice"
        :size="22"
      /></span>
      <strong>暂无符合条件的内容</strong>
      <span>请调整筛选条件，或先在采集运行中心导入数据。</span>
      <small>当前没有可加载的下一页，不显示虚构页码。</small>
    </div>

    <article
      v-for="item in items"
      :key="item.id"
      class="content-row"
    >
      <label class="check"><input
        type="checkbox"
        :checked="selectedIds.includes(item.id)"
        :aria-label="`选择 ${contentSummary(item.title, item.text)}`"
        @change="$emit('toggle', item.id)"
      ></label>
      <div class="content-copy">
        <strong>{{ contentSummary(item.title, item.text) }}</strong>
        <p>{{ item.text || '无正文' }}</p>
        <small>external_content_id: {{ item.external_content_id }}</small>
      </div>
      <div class="analysis-cell">
        <div class="analysis-badges">
          <span
            v-if="relevanceText(item)"
            :class="relevanceClass(item)"
          >{{ relevanceText(item) }}</span>
          <span
            v-if="item.analysis.status === 'completed'"
            :class="sentimentClass(item.analysis.sentiment)"
          >{{ item.analysis.sentiment || '未判定' }}</span>
          <span
            v-else
            class="status-badge status-badge--neutral"
          >{{ item.analysis.status === 'stale' ? '需重新打标' : '未打标' }}</span>
        </div>
        <div
          data-testid="content-labels"
          class="label-summary"
        >
          <span v-if="labels(item).length">{{ labels(item).map(labelPairText).join(' · ') }}</span>
          <span
            v-else
            class="empty-label"
          >暂无 AI 标签</span>
        </div>
        <small class="analysis-meta">{{ analysisMeta(item) }}</small>
      </div>
      <div class="metrics">
        <strong>{{ formatNumber(item.metrics.like_count) }} · {{ formatNumber(item.metrics.comment_count) }} · {{ formatNumber(item.metrics.share_count ?? item.metrics.repost_count) }}</strong>
        <span>赞 · 评 · 转</span>
      </div>
      <div class="source">
        <strong>{{ platformLabel(item.platform) }}</strong>
        <span>{{ item.author_display_name || '未知作者' }}</span>
      </div>
      <time>
        <strong>{{ dateTimeParts(item.published_at)[0] }}</strong>
        <span>{{ dateTimeParts(item.published_at)[1] }}</span>
      </time>
      <div class="row-actions">
        <button
          class="detail-button"
          type="button"
          @click="$emit('detail', item.id)"
        >
          查看详情
        </button>
        <button
          v-if="reviewDecision(item)"
          :class="reviewClass(item)"
          type="button"
          :disabled="reviewing"
          @click="runReview(item)"
        >
          {{ relevanceReviewActionLabel(reviewDecision(item)!) }}
        </button>
      </div>
    </article>
  </section>
</template>

<style scoped>
.content-list { overflow-x: auto; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); background: var(--aima-surface); }
.table-head,
.content-row { display: grid; min-width: 1166px; grid-template-columns: 28px 390px 245px 120px 130px 120px 85px; column-gap: 8px; align-items: center; }
.table-head { min-height: 40px; padding: 0 10px; color: var(--aima-text-muted); background: #fafbfc; font-size: 11px; font-weight: 500; }
.content-row { min-height: 74px; padding: 0 10px; border-top: 1px solid var(--aima-border); }
.check { display: grid; place-items: center; }
.check input { width: 16px; height: 16px; accent-color: var(--aima-primary); }
.content-copy,
.analysis-cell,
.source,
time { min-width: 0; }
.content-copy { display: grid; gap: 4px; padding-right: 12px; }
.content-copy strong,
.content-copy p,
.content-copy small,
.label-summary,
.analysis-meta,
.source span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.content-copy strong { color: var(--aima-text); font-size: 12px; font-weight: 500; }
.content-copy p { margin: 0; color: var(--aima-text-muted); font-size: 10px; }
.content-copy small { color: var(--aima-text-disabled); font-size: 9px; }
.analysis-cell { display: grid; gap: 4px; padding-right: 8px; }
.analysis-badges { display: flex; min-height: 20px; align-items: center; gap: 5px; }
.status-badge { display: inline-flex; min-height: 20px; align-items: center; padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 500; }
.status-badge--positive { color: #12804b; background: #e8fff3; }
.status-badge--negative { color: #f04438; background: #fff1f0; }
.status-badge--neutral { color: var(--aima-text-muted); background: #f2f4f7; }
.label-summary { color: var(--aima-text-muted); font-size: 10px; }
.empty-label,
.analysis-meta { color: var(--aima-text-disabled); font-size: 9px; }
.metrics { display: grid; gap: 4px; font-size: 10px; }
.metrics strong { color: var(--aima-text); font-weight: 500; }
.metrics span { color: var(--aima-text-disabled); font-size: 9px; }
.source { display: grid; gap: 4px; }
.source strong { color: var(--aima-text); font-size: 10px; font-weight: 500; }
.source span { color: var(--aima-text-muted); font-size: 9px; }
time { display: grid; gap: 4px; color: var(--aima-text); font-size: 9px; font-style: normal; }
time strong { font-size: 10px; font-weight: 500; }
time span { color: var(--aima-text-muted); }
.row-actions { display: grid; justify-items: start; gap: 7px; }
.detail-button,
.review-button { padding: 0; border: 0; background: transparent; cursor: pointer; font-size: 10px; line-height: 14px; text-align: left; }
.detail-button { color: var(--aima-primary); font-weight: 500; }
.review-button { color: var(--aima-text-muted); }
.review-button--relevant { color: #12804b; }
.review-button--irrelevant { color: #f04438; }
.review-button--undo { color: var(--aima-text-muted); }
.review-button:disabled { cursor: not-allowed; opacity: .55; }
.table-state { display: flex; min-height: 376px; flex-direction: column; align-items: center; justify-content: center; gap: 10px; color: var(--aima-text-muted); text-align: center; }
.table-state strong { color: var(--aima-text); font-size: 16px; }
.table-state span { font-size: 12px; }
.table-state small { color: var(--aima-text-disabled); font-size: 10px; }
.table-state--loading { gap: 14px; }
.table-state--loading span { font-size: 11px; }
.empty-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 50%; color: var(--aima-text-disabled); background: #f2f4f7; }
.skeleton { height: 14px; border-radius: 999px; background: #f2f4f7; }
.skeleton--long { width: 360px; }
.skeleton--medium { width: 320px; }
.skeleton--short { width: 280px; }
</style>
