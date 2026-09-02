import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const generated = vi.hoisted(() => ({
  getCurrentPrincipal: vi.fn(),
  listNotifications: vi.fn(),
  markNotificationsRead: vi.fn(),
}))

vi.mock('../src/generated/api/client', () => generated)

import { useIdentityStore } from '../src/features/identity/store'

describe('identity and principal inbox', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('derives administrator visibility only from the backend principal', async () => {
    generated.getCurrentPrincipal.mockResolvedValue({
      principal_id: 'local-administrator',
      display_name: '本地管理员',
      role: 'administrator',
      source: 'development',
      is_administrator: true,
    })
    const store = useIdentityStore()

    await store.ensurePrincipal()

    expect(store.isAdministrator).toBe(true)
    expect(generated.getCurrentPrincipal).toHaveBeenCalledTimes(1)
    await store.ensurePrincipal()
    expect(generated.getCurrentPrincipal).toHaveBeenCalledTimes(1)
  })

  it('loads and marks only current-principal notifications', async () => {
    const notification = {
      id: '01991f80-6d5d-7dc8-95cb-c67c12345678',
      event_type: 'data_export_succeeded',
      title: '导出完成',
      message: '导出文件已就绪。',
      is_read: false,
      created_at: '2026-09-02T10:00:00+08:00',
    }
    generated.listNotifications
      .mockResolvedValueOnce({ items: [notification], unread_count: 1 })
      .mockResolvedValueOnce({ items: [{ ...notification, is_read: true }], unread_count: 0 })
    generated.markNotificationsRead.mockResolvedValue({ requested_count: 1, changed_count: 1 })
    const store = useIdentityStore()

    await store.refreshNotifications()
    await store.markRead(['01991f80-6d5d-7dc8-95cb-c67c12345678'])

    expect(generated.listNotifications).toHaveBeenCalledTimes(2)
    expect(generated.listNotifications).toHaveBeenLastCalledWith({ limit: 50 })
    expect(generated.markNotificationsRead).toHaveBeenCalledWith({
      item_ids: ['01991f80-6d5d-7dc8-95cb-c67c12345678'],
    })
    expect(store.notifications[0]?.is_read).toBe(true)
    expect(store.unreadCount).toBe(0)
  })
})
