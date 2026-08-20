import type { ImportBatchStatus, ImportStage } from '../../generated/api/client'

export const statusLabels: Record<ImportBatchStatus, string> = {
  queued: '排队中',
  running: '处理中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

export const stageLabels: Record<ImportStage, string> = {
  queued: '等待处理',
  reading: 'Excel 读取',
  mapping: '字段映射',
  filtering: '相关性过滤',
  deduplicating: '去重',
  ingesting: '内容入库',
  succeeded: '已完成',
  failed: '处理失败',
  cancelled: '已取消',
}

export function formatNumber(value: number | undefined): string {
  return new Intl.NumberFormat('zh-CN').format(value ?? 0)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export function elapsed(start: string | null | undefined, end: string | null | undefined): string {
  if (!start) return '—'
  const seconds = Math.max(0, Math.floor((new Date(end ?? Date.now()).getTime() - new Date(start).getTime()) / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  return [hours, minutes, rest].map((part) => String(part).padStart(2, '0')).join(':')
}

export function shortId(value: string): string {
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value
}
