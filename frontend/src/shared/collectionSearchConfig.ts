import type {
  CollectionSearchCapabilityResponse,
  CollectionSearchConfig,
} from '../generated/api/client'

export type CollectionSearchConfigKey = keyof CollectionSearchConfig

export interface CollectionSearchConfigField {
  key: CollectionSearchConfigKey
  label: string
  options: string[]
}

const fieldDefinitions: {
  key: CollectionSearchConfigKey
  label: string
  capabilityKey: keyof CollectionSearchCapabilityResponse
}[] = [
  { key: 'sort_mode', label: '排序', capabilityKey: 'supported_sort_modes' },
  { key: 'published_within', label: '发布时间', capabilityKey: 'supported_time_filters' },
  { key: 'duration', label: '内容时长', capabilityKey: 'supported_duration_filters' },
  { key: 'content_type', label: '内容类型', capabilityKey: 'supported_content_types' },
]

const optionLabels: Record<string, string> = {
  general: '综合',
  latest: '最新',
  most_liked: '最多点赞',
  most_commented: '最多评论',
  most_collected: '最多收藏',
  english_preferred: '英文优先',
  hot: '热门',
  play_count: '播放最多',
  danmaku_count: '弹幕最多',
  all: '不限',
  '1d': '一天内',
  day: '一天内',
  hour: '一小时内',
  '7d': '一周内',
  week: '一周内',
  month: '一月内',
  '180d': '半年内',
  under_1m: '1 分钟内',
  '1_5m': '1—5 分钟',
  over_5m: '5 分钟以上',
  video: '视频',
  image: '图文',
}

export function collectionSearchConfigFields(
  capability: CollectionSearchCapabilityResponse,
): CollectionSearchConfigField[] {
  return fieldDefinitions.flatMap((definition) => {
    const value = capability[definition.capabilityKey]
    if (!Array.isArray(value) || value.length === 0) return []
    return [{ key: definition.key, label: definition.label, options: value }]
  })
}

export function collectionSearchOptionLabel(value: string): string {
  return optionLabels[value] ?? value
}

export function fixedCollectionSearchConfig(
  capability: CollectionSearchCapabilityResponse,
): CollectionSearchConfig {
  return Object.fromEntries(
    collectionSearchConfigFields(capability)
      .filter((field) => field.options.length === 1)
      .map((field) => [field.key, field.options[0]]),
  )
}

export function isCollectionSearchConfigComplete(
  capability: CollectionSearchCapabilityResponse,
  config: CollectionSearchConfig | undefined,
): boolean {
  return collectionSearchConfigFields(capability).every((field) => {
    const value = config?.[field.key]
    return typeof value === 'string' && field.options.includes(value)
  })
}

export function collectionSearchConfigSummary(config: CollectionSearchConfig): string {
  const values = fieldDefinitions.flatMap((field) => {
    const value = config[field.key]
    return value ? [`${field.label}：${collectionSearchOptionLabel(value)}`] : []
  })
  return values.length > 0 ? values.join(' · ') : '历史计划：沿用兼容默认（不限时间）'
}
