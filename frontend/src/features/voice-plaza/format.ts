import type { ContentLabelPairResponse } from '../../generated/api/client'
export { platformLabel } from '../../shared/domain/platform'

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export function formatNumber(value: number | null | undefined): string {
  return value == null ? '—' : new Intl.NumberFormat('zh-CN').format(value)
}

export function labelPairText(label: ContentLabelPairResponse): string {
  return `${label.primary_label} / ${label.secondary_label}`
}

export function contentSummary(title?: string | null, text?: string | null): string {
  return title?.trim() || text?.trim() || '无文本内容'
}
