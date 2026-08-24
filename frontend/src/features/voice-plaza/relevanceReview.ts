import type {
  ContentListItemResponse,
  ContentRelevanceReviewRequestDecision,
} from '../../generated/api/client'

export type RelevanceReviewDecision = ContentRelevanceReviewRequestDecision

export function relevanceReviewDecision(
  item: ContentListItemResponse,
): RelevanceReviewDecision | null {
  if (item.relevance_source === 'manual_review' && item.effective_relevance) return 'inherit_ai'
  if (
    item.relevance_source !== 'ai'
    || item.analysis.status !== 'completed'
    || !item.analysis.relevance
  ) return null
  return item.analysis.relevance === 'relevant' ? 'irrelevant' : 'relevant'
}

export function relevanceReviewActionLabel(decision: RelevanceReviewDecision): string {
  if (decision === 'relevant') return '人工标记为相关'
  if (decision === 'irrelevant') return '人工标记为不相关'
  return '撤销人工判断'
}

export function relevanceBadgeLabel(item: ContentListItemResponse): string | null {
  if (item.relevance_source === 'manual_review') {
    if (item.effective_relevance === 'relevant') return '人工复核相关'
    if (item.effective_relevance === 'irrelevant') return '人工复核不相关'
  }
  if (
    item.relevance_source === 'ai'
    && item.analysis.status === 'completed'
    && item.analysis.relevance === 'irrelevant'
  ) return 'AI 判定不相关'
  return null
}
