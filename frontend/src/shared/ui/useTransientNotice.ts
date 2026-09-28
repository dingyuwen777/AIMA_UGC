import { onScopeDispose, ref } from 'vue'

const DEFAULT_NOTICE_DURATION_MS = 3_000

/** 管理普通成功/信息确认的短时生命周期；错误、进度和警告应继续使用独立状态。 */
export function useTransientNotice(durationMs = DEFAULT_NOTICE_DURATION_MS) {
  const message = ref<string | null>(null)
  let timer: ReturnType<typeof setTimeout> | undefined

  function clear(): void {
    if (timer) clearTimeout(timer)
    timer = undefined
    message.value = null
  }

  function show(value: string, timeoutMs = durationMs): void {
    if (timer) clearTimeout(timer)
    message.value = value
    timer = setTimeout(() => {
      timer = undefined
      message.value = null
    }, timeoutMs)
  }

  onScopeDispose(() => {
    if (timer) clearTimeout(timer)
  })

  return { message, show, clear }
}

export { DEFAULT_NOTICE_DURATION_MS }
