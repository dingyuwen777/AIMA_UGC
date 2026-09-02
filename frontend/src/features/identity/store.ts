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
  const error = ref<string | null>(null)

  const isAdministrator = computed(() => principal.value?.role === 'administrator')

  async function ensurePrincipal(): Promise<CurrentPrincipalResponse | null> {
    if (principal.value) return principal.value
    loading.value = true
    error.value = null
    try {
      principal.value = unwrapResponse(await getCurrentPrincipal())
      return principal.value
    } catch (reason) {
      error.value = apiErrorMessage(reason)
      return null
    } finally {
      loading.value = false
    }
  }

  async function refreshNotifications(): Promise<void> {
    notificationLoading.value = true
    try {
      const response = unwrapResponse(await listNotifications({ limit: 50 }))
      notifications.value = response.items
      unreadCount.value = response.unread_count
    } catch (reason) {
      error.value = apiErrorMessage(reason)
    } finally {
      notificationLoading.value = false
    }
  }

  async function markRead(itemIds: string[]): Promise<void> {
    if (itemIds.length === 0) return
    try {
      const result = unwrapResponse(await markNotificationsRead({ item_ids: itemIds }))
      const readIds = new Set(itemIds)
      notifications.value = notifications.value.map((item) =>
        readIds.has(item.id) ? { ...item, is_read: true } : item,
      )
      unreadCount.value = Math.max(0, unreadCount.value - result.changed_count)
      await refreshNotifications()
    } catch (reason) {
      error.value = apiErrorMessage(reason)
    }
  }

  return {
    principal,
    notifications,
    unreadCount,
    loading,
    notificationLoading,
    error,
    isAdministrator,
    ensurePrincipal,
    refreshNotifications,
    markRead,
  }
})
