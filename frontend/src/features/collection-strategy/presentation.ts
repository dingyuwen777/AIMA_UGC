import type { CollectionPlatform } from '../../generated/api/client'
import { PLATFORM_LABELS, PLATFORM_OPTIONS } from '../../shared/domain/platform'

export const COLLECTION_SCHEDULE_PRESETS = [
  { value: '0 * * * *', label: '每1小时' },
  { value: '0 */3 * * *', label: '每3小时' },
  { value: '0 */6 * * *', label: '每6小时' },
  { value: '0 */12 * * *', label: '每12小时' },
  { value: '0 0 * * *', label: '每天 00:00' },
] as const

/** 把后端 Cron 值映射为正式页面文案；历史自定义值保持原样，避免伪造语义。 */
export function collectionScheduleLabel(scheduleExpr: string): string {
  return COLLECTION_SCHEDULE_PRESETS.find((item) => item.value === scheduleExpr)?.label ?? scheduleExpr
}

/** 为 Collection Platform 提供当前 Feature 唯一的用户可见名称。 */
export function collectionPlatformLabel(platform: CollectionPlatform): string {
  return PLATFORM_LABELS[platform]
}

/** 把 API 的绝对时间统一转换为 Figma 约定的北京时间分钟粒度，避免展示依赖浏览器宿主时区。 */
export function formatBeijingDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export const COLLECTION_PLATFORM_OPTIONS = PLATFORM_OPTIONS as Array<{
  value: CollectionPlatform
  label: string
}>
