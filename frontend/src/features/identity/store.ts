import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  getCurrentPrincipal,
  listNotifications,
  markNotificationsRead,
  type CurrentPrincipalResponse,
  type NotificationItemResponse,
} from '../../generated/api/client'
import { apiErrorMessage, unwrapResponse } from '../../shared/api/http'

export const useIdentityStore = defineStore('identity', () => {
  const principal = ref<CurrentPrincipalResponse | null>(null)
  const notifications = ref<NotificationItemResponse[]>([])
  const unreadCount = ref(0)
  const loading = ref(false)
  const notificationLoading = ref(false)
  const principalError = ref<string | null>(null)
  const notificationError = ref<string | null>(null)

  const isAdministrator = computed(() => principal.value?.role === 'administrator')

  /** 读取当前固定开发 Principal；成功后缓存，失败只影响身份状态。 */
  async function ensurePrincipal(): Promise<CurrentPrincipalResponse | null> {
    if (principal.value) return principal.value
    loading.value = true
    principalError.value = null
    try {
      principal.value = unwrapResponse(await getCurrentPrincipal())
      return principal.value
    } catch (reason) {
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
    isAdministrator,
    ensurePrincipal,
    retryPrincipal,
    refreshNotifications,
    markRead,
  }
})
