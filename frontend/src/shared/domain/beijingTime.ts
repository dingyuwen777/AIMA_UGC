/** 将日期输入冻结为北京时间自然日的开始或结束边界。 */
export function beijingDayBoundary(
  value: string,
  boundary: 'start' | 'end',
): string | undefined {
  if (!value) return undefined
  const time = boundary === 'end' ? '23:59:59.999' : '00:00:00'
  return new Date(`${value}T${time}+08:00`).toISOString()
}
