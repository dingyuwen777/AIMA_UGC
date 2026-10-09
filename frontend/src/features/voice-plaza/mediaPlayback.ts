import { ref } from 'vue'

import type { ContentMediaPlaybackPrepareRequest, ContentMediaPlaybackResponse } from '../../generated/api/client'
import { prepareMediaPlayback } from './api'

// 这是浏览器本地观察窗口，给正式 Job 的执行预算留余量，不是 CDN 地址有效期。
const OBSERVATION_WINDOW_MS = 90_000

/** 将播放失败归一为可理解的原因，不暴露签名地址或内部异常正文。 */
export function mediaPlaybackMessage(code: string | null | undefined): string {
  if (code === 'unsupported_format') return '当前浏览器不支持此视频格式，请前往原帖查看。'
  if (code === 'cover_only') return '当前仅有视频封面，暂时无法准备播放，请前往原帖查看。'
  if (code === 'cdn_forbidden') return '平台暂时拒绝访问视频，请前往原帖查看。'
  if (code === 'cdn_not_found' || code === 'cdn_gone') return '视频地址已失效或内容已删除，请前往原帖确认。'
  if (code === 'cancelled') return '视频准备已停止，可稍后重新准备或前往原帖查看。'
  if (code === 'browser_playback_failed') return '当前视频无法播放，可能是格式不受支持或地址不可用，请前往原帖查看。'
  if (code === 'browser_playback_aborted') return '视频播放已中止，可重新准备或前往原帖查看。'
  if (code === 'observation_timeout') return '视频准备等待超时，已停止本地等待，可稍后重新准备或前往原帖查看。'
  return '暂时无法播放视频，请稍后重新准备或前往原帖查看。'
}

/** 每次显式播放最多恢复一次，按对象与请求代次隔离迟到响应。 */
export function createMediaPlayback(
  identity: () => { contentId: string; position: number },
  onTerminal: () => void,
) {
  const status = ref<'idle' | 'preparing' | 'ready' | 'unavailable' | 'cooldown'>('idle')
  const streamUrl = ref<string | null>(null)
  const message = ref('')
  const cooldownUntil = ref<string | null>(null)
  let revision = 0
  let controller: AbortController | null = null
  let timer: ReturnType<typeof setTimeout> | undefined
  let deadlineTimer: ReturnType<typeof setTimeout> | undefined
  let observedJobId: string | null = null
  let observationDeadline: number | null = null
  let recoveryUsed = false
  let sourceRevision: string | null = null
  let failedSourceRevision: string | null = null
  let terminalObserved = false

  /** 清除本地观察资源，不修改或取消服务器共享 Job。 */
  function clearObservation(): void {
    if (timer !== undefined) clearTimeout(timer)
    if (deadlineTimer !== undefined) clearTimeout(deadlineTimer)
    timer = undefined
    deadlineTimer = undefined
    observedJobId = null
    observationDeadline = null
  }

  /** 失效本地请求与定时器，保留服务器共享 Job 的执行权。 */
  function reset(): void {
    revision += 1
    controller?.abort()
    controller = null
    clearObservation()
    status.value = 'idle'
    streamUrl.value = null
    message.value = ''
    cooldownUntil.value = null
    sourceRevision = null
    failedSourceRevision = null
  }

  /** 只接受当前内容的相对同源流路径，CDN 地址不进入播放器。 */
  function apply(response: ContentMediaPlaybackResponse, current: number, observing?: string): void {
    if (current !== revision) return
    // 标签页恢复后即使请求先于到期定时器返回，也不能延长观察预算。
    if (observationDeadline !== null && Date.now() >= observationDeadline) {
      expireObservation(current)
      return
    }
    const { contentId, position } = identity()
    if (response.content_id !== contentId || response.position !== position) {
      fail('invalid_source')
      return
    }
    if (observing && response.status === 'preparing' && response.job_id !== observing) {
      fail('invalid_source')
      return
    }
    if (response.status !== 'preparing') {
      clearObservation()
      if (observing && !terminalObserved) {
        terminalObserved = true
        onTerminal()
        if (current !== revision) return
      }
    }
    cooldownUntil.value = response.cooldown_until ?? null
    if (response.status === 'ready') {
      // 原生 code=4 也可能来自 HTTP 拒绝；只有服务器可信失败允许刷新费用。
      if (failedSourceRevision === response.source_revision) {
        fail(response.failure_code ?? 'browser_playback_failed')
        return
      }
      const prefix = `/api/v1/contents/${contentId}/media/${position}/playback/stream?`
      if (!response.stream_url?.startsWith(prefix)) {
        fail('invalid_source')
        return
      }
      sourceRevision = response.source_revision
      streamUrl.value = response.stream_url
      status.value = 'ready'
      message.value = '视频已准备好，点击播放器播放。'
      return
    }
    streamUrl.value = null
    status.value = response.status
    if (response.status === 'preparing' && response.job_id && !terminalObserved) {
      // 缺少源地址时的第一次准备本身已占用本次播放唯一恢复机会。
      recoveryUsed = true
      message.value = '正在准备视频，正文和评论可继续查看。'
      if (observedJobId === null) {
        observedJobId = response.job_id
        observationDeadline = Date.now() + OBSERVATION_WINDOW_MS
        deadlineTimer = setTimeout(() => { expireObservation(current) }, OBSERVATION_WINDOW_MS)
      }
      const jobId = observedJobId
      timer = setTimeout(() => {
        timer = undefined
        void prepare({ observed_job_id: jobId }, current)
      }, 1000)
      return
    }
    if (response.status === 'preparing') {
      fail()
      return
    }
    message.value = response.status === 'cooldown'
      ? '视频暂时无法准备，请稍后重试或前往原帖查看。'
      : mediaPlaybackMessage(response.failure_code)
  }

  /** 只更新媒体区的安全错误文案，不覆盖正文或编辑状态。 */
  function fail(code?: string): void {
    clearObservation()
    streamUrl.value = null
    status.value = 'unavailable'
    message.value = mediaPlaybackMessage(code)
  }

  /** 超时只结束本地等待并失效迟到响应，绝不自动发起另一轮准备。 */
  function expireObservation(current: number): void {
    if (current !== revision) return
    revision += 1
    controller?.abort()
    controller = null
    fail('observation_timeout')
  }

  /** 使用正式准备接口取得会话，过期响应和 Abort 不提交到当前对象。 */
  async function prepare(request: ContentMediaPlaybackPrepareRequest, current: number): Promise<void> {
    if (current !== revision) return
    const { contentId, position } = identity()
    try {
      const response = await prepareMediaPlayback(contentId, position, request, controller!.signal)
      apply(response, current, request.observed_job_id ?? undefined)
    } catch {
      if (current === revision && !controller?.signal.aborted) fail()
    }
  }

  /** 显式用户意图创建本地观察周期，不自动播放或预下载视频。 */
  async function start(): Promise<void> {
    if (status.value === 'preparing' || status.value === 'ready') return
    reset()
    recoveryUsed = false
    terminalObserved = false
    controller = new AbortController()
    status.value = 'preparing'
    message.value = '正在准备视频，正文和评论可继续查看。'
    await prepare({}, revision)
  }

  /** 原生错误不区分 HTTP 与 codec，服务器验证可信失败后才允许一次恢复。 */
  async function mediaError(code: number | undefined): Promise<void> {
    if (status.value !== 'ready') return
    // 原生中止不触发付费恢复；播放器释放 src 后必须回到可显式重试状态。
    if (code === 1) {
      fail('browser_playback_aborted')
      return
    }
    if (recoveryUsed || !sourceRevision) {
      fail('cdn_unavailable')
      return
    }
    recoveryUsed = true
    failedSourceRevision = sourceRevision
    streamUrl.value = null
    status.value = 'preparing'
    message.value = '视频暂时无法播放，正在尝试恢复一次。'
    await prepare({ failed_source_revision: sourceRevision }, revision)
  }

  return { status, streamUrl, message, cooldownUntil, start, mediaError, reset }
}
