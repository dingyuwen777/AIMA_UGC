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
  sortBy?: 'published_at' | 'follower_count'
  sortDirection?: 'asc' | 'desc'
}>()
const emit = defineEmits<{
  detail: [contentId: string]
  toggle: [contentId: string]
  toggleAll: []
  review: [contentId: string, decision: RelevanceReviewDecision]
  sort: [field: 'published_at' | 'follower_count']
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
  const voiceType = item.analysis.voice_type ? `发声：${item.analysis.voice_type} · ` : ''
  if (item.analysis.status === 'stale') {
    return reviewBadge ? `AI stale · ${reviewBadge}` : 'AI stale · 需重新打标'
  }
  if (item.analysis.status !== 'completed') {
    return reviewBadge ? `AI 未完成 · ${reviewBadge}` : 'AI 未完成'
  }
  return reviewBadge
    ? `${voiceType}AI 已完成 · ${reviewBadge}`
    : `${voiceType}AI 已完成 · 人工未覆盖`
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
  const formatted = formatDateTime(value).replaceAll('/', '-')
  if (formatted === '—') return ['—', '']
  const [date, ...time] = formatted.split(/\s+/)
  return [date ?? formatted, time.join(' ')]
}

/** 使用中文紧凑单位呈现粉丝数；未知与零值保持区别。 */
function followers(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value >= 100_000_000) return `${Number((value / 100_000_000).toFixed(1))}亿`
  if (value >= 10_000) return `${Number((value / 10_000).toFixed(1))}万`
  return formatNumber(value)
}

/** 只在当前排序列显示方向，点击动作由 Store 转换为服务端查询。 */
function sortLabel(field: 'published_at' | 'follower_count'): 'none' | 'ascending' | 'descending' {
  if (props.sortBy !== field) return 'none'
  return props.sortDirection === 'asc' ? 'ascending' : 'descending'
}

/** 用既有平台名称展示原稿的单字平台标识。 */
function platformMark(platform: ContentListItemResponse['platform']): string {
  return ({ xiaohongshu: '书', douyin: '抖', weibo: '微', bilibili: 'B', kuaishou: '快' })[platform]
}
</script>

<template>
  <section
    class="content-list"
    aria-label="声音广场内容列表"
  >
    <div
      v-if="items.length > 0"
      class="table-head"
    >
      <label class="check"><input
        type="checkbox"
        :checked="items.every((item) => selectedIds.includes(item.id))"
        aria-label="选择当前已加载内容"
        @change="$emit('toggleAll')"
      ></label>
      <span>标题内容</span>
      <span
        role="columnheader"
        :aria-sort="sortLabel('follower_count')"
      >
        <button
          class="sort-button"
          type="button"
          aria-label="按粉丝数排序"
          @click="emit('sort', 'follower_count')"
        >粉丝数 <img
          src="../../../../../shared/assets/sort.svg"
          width="12"
          height="16"
          alt=""
        ></button>
      </span>
      <span>AI 分析</span><span>车型</span>
      <span
        role="columnheader"
        :aria-sort="sortLabel('published_at')"
        class="date-heading"
      >
        <button
          class="sort-button"
          type="button"
          aria-label="按发布时间排序"
          @click="emit('sort', 'published_at')"
        >日期 <img
          src="../../../../../shared/assets/sort.svg"
          width="12"
          height="16"
          alt=""
        ></button>
      </span>
      <span class="actions-heading">操作</span>
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
        name="empty"
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
        <div class="title-line">
          <span
            class="platform-mark"
            :class="`platform-mark--${item.platform}`"
            :title="platformLabel(item.platform)"
          >{{ platformMark(item.platform) }}</span>
          <button
            type="button"
            class="content-title"
            :title="contentSummary(item.title, item.text)"
            @click="emit('detail', item.id)"
          >
            {{ contentSummary(item.title, item.text) }}
          </button>
        </div>
        <p :title="item.author_display_name || '未知作者'">
          {{ item.author_display_name || '未知作者' }} · 赞 {{ formatNumber(item.metrics.like_count) }} · 评论 {{ formatNumber(item.metrics.comment_count) }} · 转发 {{ formatNumber(item.metrics.share_count ?? item.metrics.repost_count) }}
        </p>
      </div>
      <div class="fans-cell">
        <strong :title="formatNumber(item.author_follower_count)">{{ followers(item.author_follower_count) }}</strong><span>{{ platformLabel(item.platform) }}</span>
      </div>
      <div
        class="analysis-cell"
        :title="analysisMeta(item)"
      >
        <div class="analysis-badges">
          <span
            v-if="relevanceText(item)"
            :class="relevanceClass(item)"
            :title="relevanceText(item) ?? undefined"
          >{{ (item.effective_relevance ?? item.analysis.relevance) === 'relevant' ? '相关' : '不相关' }}</span>
          <span
            v-if="item.analysis.status === 'completed'"
            :class="sentimentClass(item.analysis.sentiment)"
          >{{ item.analysis.sentiment || '未判定' }}</span>
          <span
            v-else
            class="status-badge status-badge--neutral"
          >{{ item.analysis.status === 'stale' ? '需重新打标' : '未打标' }}</span>
          <span
            v-if="item.analysis.voice_type"
            class="status-badge status-badge--voice"
          >{{ item.analysis.voice_type }}</span>
          <span
            v-if="item.availability && item.availability.status !== 'available'"
            class="status-badge status-badge--neutral"
          >{{ item.availability.status }}</span>
        </div>
        <div
          data-testid="content-labels"
          class="label-summary"
        >
          <span
            v-for="label in labels(item)"
            :key="labelPairText(label)"
            class="label-tag"
            :title="labelPairText(label)"
          >{{ label.primary_label }}</span>
          <span
            v-if="!labels(item).length"
            class="empty-label"
          >暂无 AI 标签</span>
        </div>
      </div>
      <div class="vehicle-cell">
        <div
          v-for="vehicle in item.vehicles ?? []"
          :key="vehicle.vehicle_model_id"
        >
          <strong>{{ vehicle.display_name }}</strong>
          <span v-if="vehicle.series_name || vehicle.category_name">{{ [vehicle.series_name, vehicle.category_name].filter(Boolean).join(' · ') }}</span>
        </div>
        <span v-if="!item.vehicles?.length">未关联</span>
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
.content-list { overflow-x: auto; border-radius: 4px; background: var(--aima-surface); box-shadow: inset 0 0 0 1px var(--aima-border); }
.table-head, .content-row { display: grid; min-width: 1212px; grid-template-columns: 16px minmax(240px, 1fr) 80px 200px 150px 120px 120px; column-gap: 12px; align-items: center; }
.table-head > :nth-child(2), .table-head > :nth-child(4), .table-head > :nth-child(5) { text-align: center; }
.table-head { min-height: 40px; padding: 0 24px 0 8px; color: var(--aima-text-muted); background: var(--aima-color-bg-table-header); font-size: 12px; font-weight: 600; }
.content-row { min-height: 76px; padding: 16px 24px 16px 8px; border-top: 1px solid var(--aima-border); }
.check { display: grid; place-items: center; }
.check input { width: 16px; height: 16px; margin: 0; accent-color: var(--aima-primary); }
.content-copy, .analysis-cell, .fans-cell, .vehicle-cell, time { min-width: 0; }
.content-copy { display: grid; gap: 4px; }
.title-line { display: flex; align-items: center; gap: 8px; min-width: 0; }
.platform-mark { display: grid; flex: none; place-items: center; min-width: 22px; height: 22px; padding-inline: 4px; border-radius: 2px; color: #fff; background: var(--aima-primary); font-size: 12px; font-weight: 700; }
.platform-mark--douyin, .platform-mark--weibo { background: var(--aima-info); }
.platform-mark--kuaishou { background: #ff7a00; }
.platform-mark--bilibili { background: #00a1d6; }
.content-title { min-width: 0; padding: 0; border: 0; color: var(--aima-text); background: transparent; font: inherit; font-size: 13px; font-weight: 700; line-height: 20px; text-align: left; cursor: pointer; overflow-wrap: anywhere; }
.content-copy p { margin: 0; overflow: hidden; color: var(--aima-text-muted); font-size: 12px; line-height: 16px; text-overflow: ellipsis; white-space: nowrap; }
.analysis-cell { display: grid; gap: 4px; }
.analysis-badges, .label-summary { display: flex; flex-wrap: wrap; gap: 6px; min-width: 0; }
.status-badge, .label-tag { display: inline-flex; max-width: 100%; align-items: center; padding: 2px 8px; border-radius: 4px; font-size: 12px; line-height: 16px; overflow-wrap: anywhere; }
.label-tag { padding-block: 0; font-size: 11px; }
.status-badge--positive { color: var(--aima-success); background: var(--aima-color-success-bg); }
.status-badge--negative { color: var(--aima-danger); background: var(--aima-color-error-bg); }
.status-badge--neutral, .label-tag { color: var(--aima-text-muted); background: var(--aima-color-bg-hover); }
.status-badge--voice { color: var(--aima-info); background: var(--aima-color-info-bg); }
.empty-label { color: var(--aima-text-disabled); font-size: 12px; }
.fans-cell, .vehicle-cell, .vehicle-cell > div, time { display: grid; gap: 4px; }
.fans-cell strong, .vehicle-cell strong, time strong { color: var(--aima-text); font-size: 13px; font-weight: 700; line-height: 18px; }
.fans-cell span, .vehicle-cell span, time span { color: var(--aima-text-muted); font-size: 12px; line-height: 18px; }
.vehicle-cell { overflow-wrap: anywhere; }
time, .date-heading { text-align: right; }
.row-actions { position: sticky; right: 0; display: grid; justify-items: end; align-self: stretch; align-content: center; gap: 4px; background: var(--aima-surface); }
.actions-heading { position: sticky; right: 0; background: var(--aima-color-bg-table-header); text-align: right; }
.detail-button, .review-button, .sort-button { padding: 0; border: 0; background: transparent; cursor: pointer; text-align: right; }
.detail-button { color: var(--aima-text); font-size: 13px; font-weight: 700; line-height: 18px; }
.review-button { color: var(--aima-text-muted); font-size: 11px; line-height: 16px; }
.review-button--relevant { color: var(--aima-success); }
.review-button--irrelevant { color: var(--aima-danger); }
.review-button:disabled { cursor: not-allowed; opacity: .55; }
.sort-button { display: inline-flex; align-items: center; gap: 6px; color: inherit; font: inherit; }
.sort-button span { color: var(--aima-text-disabled); }
[aria-sort=ascending] .sort-button, [aria-sort=descending] .sort-button { color: var(--aima-primary); }
.content-title:focus-visible, .detail-button:focus-visible, .review-button:focus-visible, .sort-button:focus-visible { outline: 2px solid var(--aima-primary); outline-offset: 3px; }
.table-state { display: flex; min-height: 376px; flex-direction: column; align-items: center; justify-content: center; gap: 10px; color: var(--aima-text-muted); text-align: center; }
.table-state--error { min-height: 306px; }
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
