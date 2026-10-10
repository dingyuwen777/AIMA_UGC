import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { getContentDataRevision } from '../../generated/api/client'
import { useIdentityStore } from '../../features/identity/store'
import { AimaApiError, unwrapResponse } from './http'

/** 页面只观察不透明数据修订号，普通账号不读取管理任务或运行详情。 */
export const useContentRevisionStore = defineStore('content-revision', () => {
  const identity = useIdentityStore()
  const revision = ref<string | null>(null)
  let inFlight: Promise<void> | null = null
  let lastPollAt = Number.NEGATIVE_INFINITY
  let denied = false

  /** 复用原每秒检查节奏；跨页面合并请求并隔离旧账号的迟到修订号。 */
  function refresh(): Promise<void> {
    if (!identity.principal || denied) return Promise.resolve()
    if (inFlight) return inFlight
    if (Date.now() - lastPollAt < 1000) return Promise.resolve()
    lastPollAt = Date.now()
    const epoch = identity.scopeEpoch
    const pending = (async () => {
      try {
        const response = unwrapResponse(await getContentDataRevision())
        if (epoch === identity.scopeEpoch) revision.value = response.revision
      } catch (error) {
        if (epoch !== identity.scopeEpoch) return
        if (error instanceof AimaApiError && [401, 403].includes(error.status)) {
          denied = true
          void identity.revalidatePrincipal()
        }
        // 瞬时错误保留成功修订号；下一次原定时检查继续恢复。
      } finally {
        if (epoch === identity.scopeEpoch) inFlight = null
      }
    })()
    inFlight = pending
    return pending
  }

  watch(() => identity.scopeEpoch, () => {
    revision.value = null
    inFlight = null
    lastPollAt = Number.NEGATIVE_INFINITY
    denied = false
  }, { flush: 'sync' })
  return { revision, refresh }
})
