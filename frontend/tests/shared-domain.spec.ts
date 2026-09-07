import { afterEach, describe, expect, it, vi } from 'vitest'

import { beijingDayBoundary } from '../src/shared/domain/beijingTime'
import { PLATFORM_LABELS, platformLabel } from '../src/shared/domain/platform'
import { createClientIdempotencyKey } from '../src/shared/idempotency'

afterEach(() => {
  vi.unstubAllGlobals()
})

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

describe('client idempotency key', () => {
  it('prefers the browser native randomUUID implementation', () => {
    const randomUUID = vi.fn(() => '12345678-1234-4678-9234-567812345678')
    const getRandomValues = vi.fn()
    vi.stubGlobal('crypto', { randomUUID, getRandomValues })

    expect(createClientIdempotencyKey()).toBe('12345678-1234-4678-9234-567812345678')
    expect(randomUUID).toHaveBeenCalledOnce()
    expect(getRandomValues).not.toHaveBeenCalled()
  })

  it('creates a standards-compliant UUID v4 when randomUUID is unavailable', () => {
    const getRandomValues = vi.fn((values: Uint8Array) => {
      values.set(Array.from({ length: 16 }, (_value, index) => index))
      return values
    })
    vi.stubGlobal('crypto', { getRandomValues })

    expect(createClientIdempotencyKey()).toBe('00010203-0405-4607-8809-0a0b0c0d0e0f')
    expect(getRandomValues).toHaveBeenCalledOnce()
  })
})
