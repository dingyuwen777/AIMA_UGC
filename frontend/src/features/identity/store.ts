import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import {
  getCurrentPrincipal,
  listNotifications,
  logoutCurrentSession,
  markNotificationsRead,
  type CurrentPrincipalResponse,
  type NotificationItemResponse,
} from '../../generated/api/client'
import { AimaApiError, apiErrorMessage, unwrapResponse } from '../../shared/api/http'
import { invalidatePrincipalScope, principalScopeEpoch, suspendPrincipalRequests, synchronizePrincipalScope } from '../../shared/api/principalScope'

/** 登录页路径：会话失效时前端跳到这里发起飞书授权。 */
export const LOGIN_PATH = '/login'

/** 身份读取的结果：区分"没有会话（要去登录）"与"已登录但无权限（要提示）"。 */
export type PrincipalOutcome = 'ok' | 'unauthenticated' | 'forbidden' | 'error'

export const useIdentityStore = defineStore('identity', () => {
  const principal = ref<CurrentPrincipalResponse | null>(null)
  const notifications = ref<NotificationItemResponse[]>([])
  const unreadCount = ref(0)
  const loading = ref(false)
  const notificationLoading = ref(false)
  const principalError = ref<string | null>(null)
  const notificationError = ref<string | null>(null)
  /** 403：身份已确认但角色不足（或不属于任何用户组），**不能**再自动去登录。 */
  const forbidden = ref(false)
  /** 401：后端明确回答"当前会话不存在/已失效"，此时才应该跳登录页。 */
  const unauthenticated = ref(false)
  const scopeEpoch = principalScopeEpoch
  const principalScope = computed(() => principal.value
    ? JSON.stringify([principal.value.principal_id, principal.value.role, principal.value.source]) : null)
  let principalRevision = 0
  let principalRequest: Promise<CurrentPrincipalResponse | null> | null = null
  let notificationRevision = 0
  watch(scopeEpoch, () => {
    notificationRevision += 1
    notifications.value = []
    unreadCount.value = 0
    notificationLoading.value = false
    notificationError.value = null
  }, { flush: 'sync' })

  const isAdministrator = computed(() => principal.value?.role === 'administrator')
  /**
   * 最近一次身份读取的分类结果。
   *
   * ⚠️ 刻意**不改变** `ensurePrincipal()` 的返回类型（仍是 `Principal | null`）：
   * 那是既有页面与既有测试依赖的契约。401/403 的区分通过这个字段暴露给路由守卫，
   * 这样"新增能力"不会顺手改掉旧契约。
   */
  const outcome = ref<PrincipalOutcome>('ok')

  /** 把一次失败的 Principal 读取归类成 401 / 403 / 其他传输错误。 */
  function classifyFailure(reason: unknown): PrincipalOutcome {
    unauthenticated.value = false
    forbidden.value = false
    if (reason instanceof AimaApiError) {
      if (reason.status === 401) {
        unauthenticated.value = true
        return 'unauthenticated'
      }
      if (reason.status === 403) {
        // ⚠️ 关键：403 **不**置 unauthenticated。否则"无权限 → 跳登录 → 回调成功 →
        // 仍然无权限 → 再跳登录"会形成死循环（任务书 H6）。
        forbidden.value = true
        return 'forbidden'
      }
    }
    return 'error'
  }

  /** 读取当前 Principal（沿用既有契约）；结果分类见 `outcome`。 */
  async function ensurePrincipal(): Promise<CurrentPrincipalResponse | null> {
    if (principalRequest) return principalRequest
    if (principal.value) {
      outcome.value = 'ok'
      return principal.value
    }
    return revalidatePrincipal()
  }

  /** 重新核验 Cookie 所属账号；同账号保留缓存，切换/撤权立即失效旧状态。 */
  function revalidatePrincipal(): Promise<CurrentPrincipalResponse | null> {
    if (principalRequest) return principalRequest
    const revision = ++principalRevision
    loading.value = true
    principalError.value = null
    const request = (async (): Promise<CurrentPrincipalResponse | null> => {
      try {
        const loaded = unwrapResponse(await getCurrentPrincipal())
        if (revision !== principalRevision) return null
        principal.value = loaded
        synchronizePrincipalScope(principalScope.value)
        forbidden.value = false
        unauthenticated.value = false
        outcome.value = 'ok'
        return principal.value
      } catch (reason) {
        if (revision !== principalRevision) return null
        principal.value = null
        outcome.value = classifyFailure(reason)
        invalidatePrincipalScope()
        principalError.value = apiErrorMessage(reason)
        return null
      } finally {
        if (revision === principalRevision) {
          loading.value = false
          principalRequest = null
        }
      }
    })()
    principalRequest = request
    suspendPrincipalRequests(request)
    return request
  }

  /** 显式重新读取 Principal，供全局 Shell 在瞬时失败后原地恢复。 */
  async function retryPrincipal(): Promise<CurrentPrincipalResponse | null> {
    return revalidatePrincipal()
  }

  /** 退出登录立即失效本地状态，再通知服务端撤销会话。 */
  async function logout(): Promise<void> {
    principalRevision += 1
    principalRequest = null
    notificationRevision += 1
    principal.value = null
    unauthenticated.value = true
    forbidden.value = false
    outcome.value = 'unauthenticated'
    invalidatePrincipalScope()
    try {
      unwrapResponse(await logoutCurrentSession())
    } finally {
      // 服务端即便报错也要清本地状态：否则页面会停在"看着还登着"的假象里。
      principal.value = null
      loading.value = false
      notifications.value = []
      unreadCount.value = 0
      principalError.value = null
      notificationError.value = null
      forbidden.value = false
      unauthenticated.value = true
      outcome.value = 'unauthenticated'
    }
  }

  /** 读取当前 Principal 的通知列表；错误不能伪装成“暂无通知”。 */
  async function refreshNotifications(): Promise<void> {
    if (!principal.value) return
    const revision = ++notificationRevision
    const epoch = scopeEpoch.value
    notificationLoading.value = true
    notificationError.value = null
    try {
      const response = unwrapResponse(await listNotifications({ limit: 50 }))
      if (revision !== notificationRevision || epoch !== scopeEpoch.value) return
      notifications.value = response.items
      unreadCount.value = response.unread_count
    } catch (reason) {
      if (revision === notificationRevision && epoch === scopeEpoch.value) notificationError.value = apiErrorMessage(reason)
    } finally {
      if (revision === notificationRevision && epoch === scopeEpoch.value) notificationLoading.value = false
    }
  }

  /** 标记当前 Principal 的通知已读，并以服务端全量未读计数作为最终事实。 */
  async function markRead(itemIds: string[]): Promise<void> {
    if (!principal.value || itemIds.length === 0) return
    const epoch = scopeEpoch.value
    notificationError.value = null
    try {
      const result = unwrapResponse(await markNotificationsRead({ item_ids: itemIds }))
      if (epoch !== scopeEpoch.value) return
      const readIds = new Set(itemIds)
      notifications.value = notifications.value.map((item) =>
        readIds.has(item.id) ? { ...item, is_read: true } : item,
      )
      unreadCount.value = Math.max(0, unreadCount.value - result.changed_count)
      await refreshNotifications()
    } catch (reason) {
      if (epoch === scopeEpoch.value) notificationError.value = apiErrorMessage(reason)
    }
  }

  return {
    principal,
    notifications,
    unreadCount,
    loading,
    notificationLoading,
    principalError,
    notificationError,
    forbidden,
    unauthenticated,
    outcome,
    isAdministrator,
    scopeEpoch,
    principalScope,
    ensurePrincipal,
    revalidatePrincipal,
    retryPrincipal,
    logout,
    refreshNotifications,
    markRead,
  }
})
