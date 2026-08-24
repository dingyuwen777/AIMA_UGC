import type {
  ContentListItemResponse,
  ContentRelevance,
  ContentRelevanceReviewRequestDecision,
} from '../../generated/api/client'

export type RelevanceReviewDecision = ContentRelevanceReviewRequestDecision

export function relevanceReviewDecision(
  item: ContentListItemResponse,
  relevanceFilter: '' | ContentRelevance,
): RelevanceReviewDecision | null {
  if (item.analysis.status !== 'completed' || !item.analysis.relevance) return null

  if (relevanceFilter === 'irrelevant') {
    return item.analysis.relevance === 'relevant' ? 'inherit_ai' : 'relevant'
  }

  return item.analysis.relevance === 'irrelevant' ? 'inherit_ai' : 'irrelevant'
}

export function relevanceReviewActionLabel(decision: RelevanceReviewDecision): string {
  if (decision === 'relevant') return '人工标记为相关'
  if (decision === 'irrelevant') return '人工标记为不相关'
  return '撤销人工判断'
}

export function relevanceBadgeLabel(
  item: ContentListItemResponse,
  relevanceFilter: '' | ContentRelevance,
): string | null {
  if (item.analysis.status !== 'completed' || !item.analysis.relevance) return null
  if (item.analysis.relevance === 'irrelevant') {
    return relevanceFilter === 'irrelevant' ? 'AI 判定不相关' : '人工复核相关'
  }
  return relevanceFilter === 'irrelevant' ? '人工复核不相关' : null
}
