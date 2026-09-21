import type { RouteLocationNormalized } from 'vue-router'

import { useIdentityStore } from '../features/identity/store'

/** 守卫的返回类型：`true` 表示放行，对象表示改道到别的路由。 */
export type IdentityGuardResult = true | { name: string; query?: Record<string, string> }

/**
 * 身份守卫：把后端的三类回答分别处理，**关键是不制造死循环**。
 *
 * - `401`（没有可用会话）→ 跳登录页，并把当前地址记进 `return_to`
 * - `403`（已登录但无权限）→ 跳「无权限」页，**绝不**再跳登录页：
 *   授权成功也换不来权限，跳登录只会「登录 → 403 → 登录」无限循环
 * - 其他错误（后端不可达等）→ 维持既有行为，不擅自把用户踢去登录
 *
 * ⚠️ 这个函数刻意放在**独立模块**里：`app/router.ts` 在导入时就会
 * `createWebHistory()` 而依赖 `window`，把守卫留在那里会让它在纯 Node 环境
 * （现有前端测试就是 Node 环境）无法被导入测试。守卫本身与"用哪种 history"无关。
 */
export async function identityGuard(to: RouteLocationNormalized): Promise<IdentityGuardResult> {
  const identity = useIdentityStore()

  // ⚠️ 这两个页面**自身不再触发身份解析**，这是防死循环的关键一环：
  //   · /login      —— 未登录的人才来这里，再解析一次还是 401
  //   · /no-access  —— 403 的人被送到这里；若守卫在这里再解析一次，会再得到 403，
  //                    于是"送去 /no-access → 又 403 → 再送去 /no-access"无限改道。
  // 它们只是静态提示页，不需要身份也能正常显示。
  if (to.name === 'login' || to.name === 'no-access') {
    // 已登录（身份已在内存里）的人打开登录页没有意义，回首页。
    if (to.name === 'login' && identity.principal) return { name: 'home' }
    return true
  }

  await identity.ensurePrincipal()
  const outcome = identity.outcome

  if (outcome === 'unauthenticated') {
    return { name: 'login', query: { return_to: to.fullPath } }
  }
  if (outcome === 'forbidden') {
    return { name: 'no-access' }
  }
  if (to.meta.requiresAdministrator && identity.principal?.role !== 'administrator') {
    return { name: 'home', query: { access: 'administrator-required' } }
  }
  return true
}
