import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setTestPrincipal } from './rolePrincipal'

const generated = vi.hoisted(() => ({ getContentDataRevision: vi.fn() }))
vi.mock('../src/generated/api/client', () => generated)
import { useContentRevisionStore } from '../src/shared/api/contentRevision'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.resetAllMocks()
  vi.useFakeTimers()
  setTestPrincipal('user', 'A')
})
afterEach(() => vi.useRealTimers())

describe('只读内容修订号', () => {
  it('同一秒内合并跨页面读取，下一秒保持原有检查间隔', async () => {
    generated.getContentDataRevision.mockResolvedValue({ revision: 'data-1' })
    const store = useContentRevisionStore()
    await Promise.all([store.refresh(), store.refresh()])
    await store.refresh()
    expect(generated.getContentDataRevision).toHaveBeenCalledTimes(1)
    expect(store.revision).toBe('data-1')
    vi.advanceTimersByTime(1000)
    generated.getContentDataRevision.mockResolvedValue({ revision: 'data-2' })
    await store.refresh()
    expect(generated.getContentDataRevision).toHaveBeenCalledTimes(2)
    expect(store.revision).toBe('data-2')
  })

  it('账号切换不继承旧修订号，也不接收旧在途响应', async () => {
    let finish!: (value: unknown) => void
    generated.getContentDataRevision.mockReturnValueOnce(new Promise((resolve) => { finish = resolve }))
    const store = useContentRevisionStore()
    const old = store.refresh()
    setTestPrincipal('user', 'B')
    expect(store.revision).toBeNull()
    generated.getContentDataRevision.mockResolvedValue({ revision: 'B-data' })
    await store.refresh()
    finish({ revision: 'A-data' })
    await old
    expect(store.revision).toBe('B-data')
  })
})
