import type {
  ContentAnalysisStatus,
  ContentLabelPairResponse,
  ContentRelevance,
} from '../../generated/api/client'
export { platformLabel } from '../../shared/domain/platform'
export { formatDateTime } from '../../shared/domain/beijingTime'

export function formatNumber(value: number | null | undefined): string {
  return value == null ? '—' : new Intl.NumberFormat('zh-CN').format(value)
}

export function labelPairText(label: ContentLabelPairResponse): string {
  return `${label.primary_label} / ${label.secondary_label}`
}

export function contentSummary(title?: string | null, text?: string | null): string {
  return title?.trim() || text?.trim() || '无文本内容'
}

const CONTENT_TYPE_LABELS: Record<string, string> = {
  note: '笔记',
  image: '图文 / 图片',
  video: '视频',
  text: '纯文本',
  unknown: '未识别',
}

export function contentTypeLabel(value: string): string {
  return CONTENT_TYPE_LABELS[value] ?? value
}

export function relevanceLabel(value: ContentRelevance): string {
  return value === 'relevant' ? '相关' : '不相关'
}

const ANALYSIS_STATUS_LABELS: Record<ContentAnalysisStatus, string> = {
  completed: '已分析',
  pending: '未分析',
  stale: '需重新分析',
}

export function analysisStatusLabel(value: ContentAnalysisStatus): string {
  return ANALYSIS_STATUS_LABELS[value]
}
