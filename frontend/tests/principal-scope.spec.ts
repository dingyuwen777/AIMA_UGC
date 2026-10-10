import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  capturePrincipalScope, invalidatePrincipalScope, isPrincipalScopeCurrent,
  ownsPrincipalFilters, principalScopeEpoch, suspendPrincipalRequests, synchronizePrincipalScope,
} from '../src/shared/api/principalScope'
import { aimaRequest } from '../src/shared/api/request'

const workbenchKey = 'aima.workbench.applied-filters'
const voiceKey = 'aima.voice-plaza.applied-search.v1'

beforeEach(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('sessionStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value) },
    removeItem: (key: string) => { values.delete(key) },
  })
  invalidatePrincipalScope()
})
afterEach(() => vi.unstubAllGlobals())

describe('Principal 筛选归属和正式请求隔离', () => {
  it('不继承无 Owner 旧缓存，同账号复核保持原格式，角色切换清空两个快照', () => {
    sessionStorage.setItem(workbenchKey, '{"schema_version":1}')
    sessionStorage.setItem(voiceKey, '{"filters":{"platform":"douyin"}}')
    synchronizePrincipalScope('A:user')
    expect(sessionStorage.getItem(workbenchKey)).toBeNull()
    expect(sessionStorage.getItem(voiceKey)).toBeNull()
    const snapshot = '{"filters":{"platform":"douyin"},"sortBy":"published_at","sortDirection":"desc"}'
    sessionStorage.setItem(voiceKey, snapshot)
    sessionStorage.setItem(workbenchKey, '{"schema_version":1}')
    const epoch = principalScopeEpoch.value
    synchronizePrincipalScope('A:user')
    expect(principalScopeEpoch.value).toBe(epoch)
    expect(sessionStorage.getItem(voiceKey)).toBe(snapshot)
    expect(ownsPrincipalFilters()).toBe(true)
    synchronizePrincipalScope('A:administrator')
    expect(sessionStorage.getItem(workbenchKey)).toBeNull()
    expect(sessionStorage.getItem(voiceKey)).toBeNull()
    invalidatePrincipalScope()
    expect(ownsPrincipalFilters()).toBe(false)
  })

  it('A 的迟到业务响应被拒绝，B 发出的请求正常完成', async () => {
    synchronizePrincipalScope('A:user')
    let finish!: (response: Response) => void
    const fetch = vi.fn().mockImplementationOnce(() => new Promise<Response>((resolve) => { finish = resolve }))
      .mockResolvedValueOnce(Response.json({ owner: 'B' }))
    vi.stubGlobal('fetch', fetch)
    const oldRequest = aimaRequest('/api/v1/contents')
    const rejected = expect(oldRequest).rejects.toMatchObject({ name: 'AbortError' })
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
    synchronizePrincipalScope('B:user')
    finish(Response.json({ owner: 'A' }))
    await rejected
    await expect(aimaRequest('/api/v1/contents')).resolves.toEqual({ owner: 'B' })
  })

  it('Cookie 复核屏障暂停业务发送，身份接口不自等待，同账号响应保持有效', async () => {
    synchronizePrincipalScope('A:user')
    const epoch = capturePrincipalScope()
    let finish!: () => void
    const validation = new Promise<void>((resolve) => { finish = resolve })
    suspendPrincipalRequests(validation)
    const fetch = vi.fn().mockImplementation(async () => Response.json({ ok: true }))
    vi.stubGlobal('fetch', fetch)
    const business = aimaRequest('/api/v1/contents')
    await Promise.resolve()
    expect(fetch).not.toHaveBeenCalled()
    await aimaRequest('/api/v1/principal')
    expect(fetch).toHaveBeenCalledTimes(1)
    synchronizePrincipalScope('A:user')
    finish()
    await business
    expect(isPrincipalScopeCurrent(epoch)).toBe(true)
    expect(fetch).toHaveBeenCalledTimes(2)
  })
})
