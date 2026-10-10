import type { Pinia } from 'pinia'
import { useIdentityStore } from '../src/features/identity/store'
import { synchronizePrincipalScope } from '../src/shared/api/principalScope'

/** 测试显式声明账号前置事实，不让历史管理员场景隐式依赖匿名权限。 */
export function setTestPrincipal(role: 'administrator' | 'user' = 'administrator', id = 'test-principal', pinia?: Pinia): void {
  const identity = useIdentityStore(pinia)
  identity.principal = { principal_id: id, display_name: id, role, source: 'development', is_administrator: role === 'administrator' }
  synchronizePrincipalScope(identity.principalScope)
}
