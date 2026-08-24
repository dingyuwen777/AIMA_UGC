<script setup lang="ts">
import type {
  ContentLabelPairResponse,
  ContentListItemResponse,
} from '../../../../../generated/api/client'
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
  selectedIds: string[]
  reviewing: boolean
}>()
const emit = defineEmits<{
  detail: [contentId: string]
  toggle: [contentId: string]
  toggleAll: []
  review: [contentId: string, decision: RelevanceReviewDecision]
}>()

function sentimentClass(sentiment?: string | null): string {
  if (sentiment === '正面') return 'sentiment sentiment--positive'
  if (sentiment === '负面') return 'sentiment sentiment--negative'
  return 'sentiment sentiment--neutral'
}

function labels(item: ContentListItemResponse): ContentLabelPairResponse[] {
  return item.analysis.labels ?? []
}

function badge(item: ContentListItemResponse): string | null {
  return relevanceBadgeLabel(item)
}

function reviewDecision(item: ContentListItemResponse): RelevanceReviewDecision | null {
  return relevanceReviewDecision(item)
}

function reviewClass(item: ContentListItemResponse): string {
  const decision = reviewDecision(item)
  if (decision === 'irrelevant') return 'review-button review-button--irrelevant'
  if (decision === 'inherit_ai') return 'review-button review-button--undo'
  return 'review-button review-button--relevant'
}

function runReview(item: ContentListItemResponse): void {
  const decision = reviewDecision(item)
  if (decision) emit('review', item.id, decision)
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
      class="table-state"
      role="status"
    >
      正在加载内容…
    </div>
    <div
      v-else-if="items.length === 0"
      class="table-state"
    >
      <strong>暂无符合条件的内容</strong><span>请调整筛选条件，或先在采集运行中心导入数据。</span>
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
        <small>External ID: {{ item.external_content_id }}</small>
      </div>
      <div class="analysis-cell">
        <span
          v-if="badge(item)"
          class="relevance-badge"
          :class="{
            'relevance-badge--reviewed': badge(item) === '人工复核相关',
            'relevance-badge--excluded': badge(item) === '人工复核不相关',
          }"
        >{{ badge(item) }}</span>
        <span
          v-else-if="item.analysis.status === 'completed'"
          :class="sentimentClass(item.analysis.sentiment)"
        >{{ item.analysis.sentiment || '未判定' }}</span>
        <span
          v-else
          class="analysis-pending"
        >{{ item.analysis.status === 'stale' ? '需重新打标' : '未打标' }}</span>
        <div
          data-testid="content-labels"
          class="label-list"
        >
          <span
            v-for="(label, index) in labels(item)"
            :key="`${label.primary_label}:${label.secondary_label}:${index}`"
            class="label-pair"
          >{{ labelPairText(label) }}</span>
          <span
            v-if="labels(item).length === 0"
            class="empty-label"
          >暂无 AI 标签</span>
        </div>
      </div>
      <div class="metrics">
        <span>赞 {{ formatNumber(item.metrics.like_count) }}</span><span>评 {{ formatNumber(item.metrics.comment_count) }}</span><span>转 {{ formatNumber(item.metrics.share_count ?? item.metrics.repost_count) }}</span>
      </div>
      <div class="source">
        <strong>{{ platformLabel(item.platform) }}</strong><span>{{ item.author_display_name || '未知作者' }}</span><small>{{ item.source.provider_name }}</small>
      </div>
      <time>{{ formatDateTime(item.published_at) }}</time>
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
.content-list { overflow: hidden; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: #fff; }
.table-head, .content-row { display: grid; grid-template-columns: 34px minmax(280px, 2fr) minmax(260px, 1.55fr) minmax(115px, .7fr) minmax(125px, .75fr) minmax(130px, .8fr) minmax(138px, .95fr); align-items: center; }
.table-head { min-height: 46px; padding: 0 14px; border-bottom: 1px solid var(--aima-border); color: #535d6f; background: #fafbfc; font-size: 12px; font-weight: 600; }
.content-row { min-height: 112px; padding: 14px; border-bottom: 1px solid var(--aima-border); }
.content-row:last-child { border-bottom: 0; }
.check { display: grid; place-items: center; }
.check input { width: 16px; height: 16px; accent-color: var(--aima-primary); }
.content-copy { min-width: 0; padding-right: 24px; }
.content-copy strong { display: block; overflow: hidden; color: #222b3c; text-overflow: ellipsis; white-space: nowrap; }
.content-copy p { display: -webkit-box; overflow: hidden; margin: 7px 0; color: #687285; font-size: 12px; line-height: 1.55; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.content-copy small, .source small { color: #9aa1ae; font-size: 10px; }
.analysis-cell { padding-right: 16px; }
.sentiment, .analysis-pending, .relevance-badge { display: inline-block; padding: 3px 7px; border-radius: 4px; font-size: 11px; }
.sentiment--positive { color: #12804b; background: #eaf8f1; }
.sentiment--negative { color: #cf3440; background: #fff0f1; }
.sentiment--neutral, .analysis-pending { color: #667085; background: #f1f3f6; }
.relevance-badge { color: #b4232d; background: #fff0f1; }
.relevance-badge--reviewed { color: #12804b; background: #eaf8f1; }
.relevance-badge--excluded { color: #9b2c36; background: #fff0f1; }
.label-list { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; }
.label-pair { padding: 3px 7px; border: 1px solid #d9e6f7; border-radius: 4px; color: #366799; background: #f3f8ff; font-size: 10px; }
.empty-label { color: #9aa1ae; font-size: 11px; }
.metrics { display: grid; gap: 5px; color: #5f697a; font-size: 11px; }
.source strong, .source span { display: block; }
.source strong { color: #303a4c; font-size: 12px; }
.source span { overflow: hidden; margin: 5px 0; color: #697386; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
time { color: #566071; font-size: 11px; line-height: 1.6; }
.row-actions { display: grid; gap: 6px; }
.detail-button, .review-button { min-height: 32px; padding: 0 8px; border-radius: 6px; background: #fff; cursor: pointer; font-size: 11px; }
.detail-button { border: 1px solid var(--aima-primary); color: var(--aima-primary); }
.review-button--relevant { border: 1px solid #12804b; color: #12804b; }
.review-button--irrelevant { border: 1px solid #c93440; color: #b4232d; }
.review-button--undo { border: 1px solid #667085; color: #586174; }
.review-button:disabled { cursor: not-allowed; opacity: .55; }
.table-state { display: flex; min-height: 260px; flex-direction: column; align-items: center; justify-content: center; color: #8b94a5; }
.table-state strong { margin-bottom: 9px; color: #505a6c; }
</style>
