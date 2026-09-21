import { computed, ref } from 'vue'
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
    if (principal.value) {
      outcome.value = 'ok'
      return principal.value
    }
    loading.value = true
    principalError.value = null
    try {
      principal.value = unwrapResponse(await getCurrentPrincipal())
      forbidden.value = false
      unauthenticated.value = false
      outcome.value = 'ok'
      return principal.value
    } catch (reason) {
      outcome.value = classifyFailure(reason)
      principalError.value = apiErrorMessage(reason)
      return null
    } finally {
      loading.value = false
    }
  }

  /** 显式重新读取 Principal，供全局 Shell 在瞬时失败后原地恢复。 */
  async function retryPrincipal(): Promise<CurrentPrincipalResponse | null> {
    principal.value = null
    return ensurePrincipal()
  }

  /** 退出登录：先让**服务端**撤销会话，再清空本地身份状态。 */
  async function logout(): Promise<void> {
    try {
      await logoutCurrentSession()
    } finally {
      // 服务端即便报错也要清本地状态：否则页面会停在"看着还登着"的假象里。
      principal.value = null
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
    notificationLoading.value = true
    notificationError.value = null
    try {
      const response = unwrapResponse(await listNotifications({ limit: 50 }))
      notifications.value = response.items
      unreadCount.value = response.unread_count
    } catch (reason) {
      notificationError.value = apiErrorMessage(reason)
    } finally {
      notificationLoading.value = false
    }
  }

  /** 标记当前 Principal 的通知已读，并以服务端全量未读计数作为最终事实。 */
  async function markRead(itemIds: string[]): Promise<void> {
    if (itemIds.length === 0) return
    notificationError.value = null
    try {
      const result = unwrapResponse(await markNotificationsRead({ item_ids: itemIds }))
      const readIds = new Set(itemIds)
      notifications.value = notifications.value.map((item) =>
        readIds.has(item.id) ? { ...item, is_read: true } : item,
      )
      unreadCount.value = Math.max(0, unreadCount.value - result.changed_count)
      await refreshNotifications()
    } catch (reason) {
      notificationError.value = apiErrorMessage(reason)
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
    ensurePrincipal,
    retryPrincipal,
    logout,
    refreshNotifications,
    markRead,
  }
})
