/** 将日期输入冻结为北京时间自然日的开始或结束边界。 */
export function beijingDayBoundary(
  value: string,
  boundary: 'start' | 'end',
): string | undefined {
  if (!value) return undefined
  const time = boundary === 'end' ? '23:59:59.999' : '00:00:00'
  return new Date(`${value}T${time}+08:00`).toISOString()
}

/** 使用产品统一的北京时间格式展示绝对时间。 */
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
