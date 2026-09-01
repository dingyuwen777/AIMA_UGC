import { describe, expect, it } from 'vitest'

import { beijingDayBoundary } from '../src/shared/domain/beijingTime'
import { PLATFORM_LABELS, platformLabel } from '../src/shared/domain/platform'

describe('shared domain presentation', () => {
  it('keeps the five canonical platform names in one owner', () => {
    expect(PLATFORM_LABELS).toEqual({
      xiaohongshu: '小红书',
      douyin: '抖音',
      weibo: '微博',
      bilibili: 'B站',
      kuaishou: '快手',
    })
    expect(platformLabel('bilibili')).toBe('B站')
    expect(platformLabel('unknown-provider')).toBe('unknown-provider')
  })

  it('freezes inclusive Beijing natural-day boundaries', () => {
    expect(beijingDayBoundary('2026-09-01', 'start')).toBe('2026-08-31T16:00:00.000Z')
    expect(beijingDayBoundary('2026-09-01', 'end')).toBe('2026-09-01T15:59:59.999Z')
    expect(beijingDayBoundary('', 'start')).toBeUndefined()
  })
})
