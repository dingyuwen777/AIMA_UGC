import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AimaApiError } from '../src/shared/api/http'

const generated = vi.hoisted(() => ({
  getCurrentPrincipal: vi.fn(),
  listNotifications: vi.fn(),
  markNotificationsRead: vi.fn(),
  logoutCurrentSession: vi.fn(),
}))

vi.mock('../src/generated/api/client', () => generated)

import { useIdentityStore } from '../src/features/identity/store'
import { identityGuard } from '../src/app/identity-guard'
import { routes } from '../src/app/routes'

/** 构造一个后端 401：会话不存在 / 过期 / 已撤销。 */
function unauthorized(): AimaApiError {
  return new AimaApiError({
    type: 'https://aima.example/problems/authentication_required',
    title: '需要登录',
    status: 401,
    detail: '当前会话不存在或已失效，请重新登录。',
    request_id: 'req-401',
    errors: [{ field: null, code: 'authentication_required', message: '需要登录' }],
  })
}

/** 构造一个后端 403：已登录但角色不足 / 不属于任何用户组。 */
function forbidden(): AimaApiError {
  return new AimaApiError({
    type: 'https://aima.example/problems/feishu_group_required',
    title: '没有访问权限',
    status: 403,
    detail: '当前账号不在允许使用本系统的用户组内。',
    request_id: 'req-403',
    errors: [{ field: null, code: 'feishu_group_required', message: '无权限' }],
  })
}

function locationOf(to: unknown): { name?: string; query?: Record<string, string> } {
  return to as { name?: string; query?: Record<string, string> }
}

describe('身份失败分类（401 → 登录，403 → 无权限，且不成环）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('401 归类为未登录，供守卫跳登录页', async () => {
    generated.getCurrentPrincipal.mockRejectedValue(unauthorized())
    const store = useIdentityStore()

    expect(await store.ensurePrincipal()).toBeNull()
    expect(store.outcome).toBe('unauthenticated')
    expect(store.unauthenticated).toBe(true)
    // 401 不是"无权限"，两者不能混。
    expect(store.forbidden).toBe(false)
  })

  it('403 归类为无权限，且 **不会** 被当成未登录', async () => {
    generated.getCurrentPrincipal.mockRejectedValue(forbidden())
    const store = useIdentityStore()

    expect(await store.ensurePrincipal()).toBeNull()
    expect(store.outcome).toBe('forbidden')
    expect(store.forbidden).toBe(true)
    // ⚠️ 这条是 H6 死循环防线的核心：403 绝不能被解释成"去登录"。
    expect(store.unauthenticated).toBe(false)
  })

  it('后端不可达时不擅自判定为未登录', async () => {
    generated.getCurrentPrincipal.mockRejectedValue(new Error('network down'))
    const store = useIdentityStore()

    expect(await store.ensurePrincipal()).toBeNull()
    expect(store.outcome).toBe('error')
    expect(store.unauthenticated).toBe(false)
    expect(store.forbidden).toBe(false)
    expect(store.principalError).toContain('network down')
  })

  it('登出会清空本地身份状态并调用服务端撤销', async () => {
    generated.getCurrentPrincipal.mockResolvedValue({
      principal_id: 'p-1',
      display_name: '张三',
      role: 'user',
      source: 'feishu',
    })
    generated.logoutCurrentSession.mockResolvedValue(undefined)
    const store = useIdentityStore()
    await store.ensurePrincipal()

    await store.logout()

    expect(generated.logoutCurrentSession).toHaveBeenCalledTimes(1)
    expect(store.principal).toBeNull()
  })

  it('服务端登出失败也要清掉本地状态（不能假装还登着）', async () => {
    generated.getCurrentPrincipal.mockResolvedValue({
      principal_id: 'p-1',
      display_name: '张三',
      role: 'user',
      source: 'feishu',
    })
    generated.logoutCurrentSession.mockRejectedValue(new Error('offline'))
    const store = useIdentityStore()
    await store.ensurePrincipal()

    await expect(store.logout()).rejects.toThrow('offline')

    expect(store.principal).toBeNull()
  })

  it('服务端用错误 Contract 回答登出失败时也不能误判成成功', async () => {
    generated.getCurrentPrincipal.mockResolvedValue({
      principal_id: 'p-1',
      display_name: '张三',
      role: 'user',
      source: 'feishu',
    })
    generated.logoutCurrentSession.mockResolvedValue({
      type: 'https://aima.example/problems/logout-failed',
      title: '登出失败',
      status: 503,
      detail: '会话服务暂时不可用',
      request_id: 'req-logout-failed',
      errors: [],
    })
    const store = useIdentityStore()
    await store.ensurePrincipal()

    await expect(store.logout()).rejects.toMatchObject({ status: 503 })

    expect(store.principal).toBeNull()
    expect(store.outcome).toBe('unauthenticated')
  })
})

describe('路由守卫：401 跳登录、403 跳无权限且不循环', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('401 时改道登录页并带上 return_to', async () => {
    generated.getCurrentPrincipal.mockRejectedValue(unauthorized())

    const result = locationOf(
      await identityGuard({ name: 'voice-plaza', fullPath: '/voice-plaza?x=1', meta: {} } as never),
    )

    expect(result.name).toBe('login')
    expect(result.query?.return_to).toBe('/voice-plaza?x=1')
  })

  it('403 时改道无权限页，**且不去登录页**', async () => {
    generated.getCurrentPrincipal.mockRejectedValue(forbidden())

    const result = locationOf(
      await identityGuard({ name: 'home', fullPath: '/', meta: {} } as never),
    )

    expect(result.name).toBe('no-access')
    expect(result.name).not.toBe('login')
  })

  it('403 之后停在无权限页不会再次触发身份读取（无死循环）', async () => {
    generated.getCurrentPrincipal.mockRejectedValue(forbidden())

    // 第一次：被改道到无权限页
    const first = locationOf(
      await identityGuard({ name: 'home', fullPath: '/', meta: {} } as never),
    )
    expect(first.name).toBe('no-access')

    // 第二次：守卫处理无权限页本身时必须**直接放行**，不再拉取身份。
    // 否则会「送去 /no-access → 又 403 → 再送去 /no-access」无限改道。
    generated.getCurrentPrincipal.mockClear()
    const second = await identityGuard({
      name: 'no-access',
      fullPath: '/no-access',
      meta: {},
    } as never)

    expect(second).toBe(true)
    expect(generated.getCurrentPrincipal).not.toHaveBeenCalled()
  })

  it('未登录时停在登录页也不会再次触发身份读取', async () => {
    generated.getCurrentPrincipal.mockRejectedValue(unauthorized())
    await identityGuard({ name: 'home', fullPath: '/', meta: {} } as never)

    generated.getCurrentPrincipal.mockClear()
    const onLogin = await identityGuard({
      name: 'login',
      fullPath: '/login',
      meta: {},
    } as never)

    expect(onLogin).toBe(true)
    expect(generated.getCurrentPrincipal).not.toHaveBeenCalled()
  })

  it('登录页在已登录时回首页，未登录时正常展示', async () => {
    generated.getCurrentPrincipal.mockResolvedValue({
      principal_id: 'p-1',
      display_name: '张三',
      role: 'user',
      source: 'feishu',
    })
    const store = useIdentityStore()
    await store.ensurePrincipal()

    const result = locationOf(
      await identityGuard({ name: 'login', fullPath: '/login', meta: {} } as never),
    )
    expect(result.name).toBe('home')
  })

  it('管理员路由守卫保持既有行为（非管理员回首页并带 access 提示）', async () => {
    generated.getCurrentPrincipal.mockResolvedValue({
      principal_id: 'p-1',
      display_name: '张三',
      role: 'user',
      source: 'feishu',
    })

    const result = locationOf(
      await identityGuard({
        name: 'admin-configuration',
        fullPath: '/admin/configuration',
        meta: { requiresAdministrator: true },
      } as never),
    )

    expect(result.name).toBe('home')
    expect(result.query?.access).toBe('administrator-required')
  })
})

describe('登录与无权限页面已注册（D11/D12 的前端入口）', () => {
  it('注册了 login 与 no-access 两条路由', () => {
    expect(routes).toContainEqual(
      expect.objectContaining({ path: '/login', name: 'login' }),
    )
    expect(routes).toContainEqual(
      expect.objectContaining({ path: '/no-access', name: 'no-access' }),
    )
  })

})
