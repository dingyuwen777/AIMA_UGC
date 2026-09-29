import { effectScope } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useTransientNotice } from '../src/shared/ui/useTransientNotice'

afterEach(() => {
  vi.useRealTimers()
})

describe('通用瞬时提示', () => {
  it('普通成功提示默认三秒自动清除，并由 scope 统一回收计时器', () => {
    vi.useFakeTimers()
    const scope = effectScope()
    const notice = scope.run(() => useTransientNotice())
    expect(notice).toBeDefined()

    notice!.show('工作台布局已保存。')
    expect(notice!.message.value).toBe('工作台布局已保存。')
    vi.advanceTimersByTime(2_999)
    expect(notice!.message.value).toBe('工作台布局已保存。')
    vi.advanceTimersByTime(1)
    expect(notice!.message.value).toBeNull()

    scope.stop()
  })

  it('新提示替换旧计时器，旧计时器不能提前清除新内容', () => {
    vi.useFakeTimers()
    const scope = effectScope()
    const notice = scope.run(() => useTransientNotice())!

    notice.show('第一条')
    vi.advanceTimersByTime(2_000)
    notice.show('第二条')
    vi.advanceTimersByTime(1_000)
    expect(notice.message.value).toBe('第二条')
    vi.advanceTimersByTime(2_000)
    expect(notice.message.value).toBeNull()

    scope.stop()
  })
})
