import { ref } from 'vue'

const FILTER_KEYS = ['aima.workbench.applied-filters', 'aima.voice-plaza.applied-search.v1']
const OWNER_KEY = 'aima.applied-filters.principal.v1'
export const principalScopeEpoch = ref(0)
let currentScope: string | null = null
let requestEpoch = 0
let validation: Promise<unknown> | null = null

/** 读取账号请求代次；同账号重新验证不改变有效响应归属。 */
export function capturePrincipalScope(): number { return requestEpoch }

/** 旧账号发出的响应不能进入当前状态。 */
export function isPrincipalScopeCurrent(epoch: number): boolean { return epoch === requestEpoch }

/** 身份待复核时暂停业务发送，Cookie 跨标签页切换后先确认 Owner。 */
export function suspendPrincipalRequests(pending: Promise<unknown>): void {
  validation = pending
  void pending.finally(() => { if (validation === pending) validation = null })
}

/** 等待当前身份读取完成，身份接口自身不等待此屏障。 */
export async function waitForPrincipalValidation(): Promise<void> {
  let pending = validation
  while (pending) {
    await pending
    if (validation === pending) return
    pending = validation
  }
}

/** 只变更独立 Owner 标记，不改变原有两个筛选快照格式。 */
export function synchronizePrincipalScope(scope: string | null): void {
  const changed = scope !== currentScope
  currentScope = scope
  try {
    const previous = sessionStorage.getItem(OWNER_KEY)
    if (!scope || previous !== scope) FILTER_KEYS.forEach((key) => sessionStorage.removeItem(key))
    if (scope) sessionStorage.setItem(OWNER_KEY, scope)
    else sessionStorage.removeItem(OWNER_KEY)
  } catch { /* 禁用存储时仍按内存代次隔离账号。 */ }
  if (changed) {
    requestEpoch += 1
    principalScopeEpoch.value += 1
  }
}

/** 未绑定当前 Principal 的旧筛选缓存不允许被恢复或写回。 */
export function ownsPrincipalFilters(): boolean {
  try { return currentScope !== null && sessionStorage.getItem(OWNER_KEY) === currentScope }
  catch { return false }
}

/** 登出立即撤销所有在途提交权，并清空本标签页的账号筛选。 */
export function invalidatePrincipalScope(): void {
  requestEpoch += 1
  synchronizePrincipalScope(null)
}
