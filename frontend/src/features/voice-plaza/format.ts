import type { ContentLabelPairResponse } from '../../generated/api/client'
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
