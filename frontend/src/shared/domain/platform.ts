export const PLATFORM_LABELS = {
  xiaohongshu: '小红书',
  douyin: '抖音',
  weibo: '微博',
  bilibili: 'B站',
  kuaishou: '快手',
} as const

export type SupportedPlatform = keyof typeof PLATFORM_LABELS

export const PLATFORM_OPTIONS = Object.entries(PLATFORM_LABELS).map(([value, label]) => ({
  value: value as SupportedPlatform,
  label,
}))

/** 将平台机器身份转换为统一中文名称；未知值保留原文以便排障。 */
export function platformLabel(platform: string): string {
  return PLATFORM_LABELS[platform.toLowerCase() as SupportedPlatform] ?? platform
}
