export const PLATFORM_LABELS = {
  xiaohongshu: '小红书',
  douyin: '抖音',
  weibo: '微博',
  bilibili: 'B站',
  kuaishou: '快手',
} as const

export type SupportedPlatform = keyof typeof PLATFORM_LABELS

/** 平台图标/角标的统一品牌色；各功能模块共用这一份映射，避免颜色散落硬编码。 */
export const PLATFORM_COLORS: Record<SupportedPlatform, string> = {
  xiaohongshu: '#ff2442', // 小红书红
  douyin: '#000000', // 抖音黑
  weibo: '#ff8200', // 微博橙
  bilibili: '#00a1d6', // B站蓝
  kuaishou: '#ff4906', // 快手橙红
}

/** 五个平台的身份键；作为“支持平台列表”的唯一来源，供各 Feature 复用，避免重复硬编码。 */
export const PLATFORM_KEYS = Object.keys(PLATFORM_LABELS) as SupportedPlatform[]

export const PLATFORM_OPTIONS = Object.entries(PLATFORM_LABELS).map(([value, label]) => ({
  value: value as SupportedPlatform,
  label,
}))

/** 将平台机器身份转换为统一中文名称；未知值保留原文以便排障。 */
export function platformLabel(platform: string): string {
  return PLATFORM_LABELS[platform.toLowerCase() as SupportedPlatform] ?? platform
}

/** 将平台机器身份转换为统一品牌色；未知平台回退到品牌主色，保证始终有可见底色。 */
export function platformColor(platform: string): string {
  return PLATFORM_COLORS[platform.toLowerCase() as SupportedPlatform] ?? 'var(--aima-primary)'
}
