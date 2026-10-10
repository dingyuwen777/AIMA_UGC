import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ContentMediaPlaybackResponse } from '../src/generated/api/client'
import { prepareMediaPlayback } from '../src/features/voice-plaza/api'
import { createMediaPlayback, mediaPlaybackMessage } from '../src/features/voice-plaza/mediaPlayback'

vi.mock('../src/features/voice-plaza/api', () => ({
  prepareMediaPlayback: vi.fn(),
}))

const contentId = '01991f80-6d5d-7dc8-95cb-c67c12345670'
const firstRevision = 'a'.repeat(64)
const secondRevision = 'b'.repeat(64)
const jobId = '10000000-0000-4000-8000-000000000001'

/** 使用生成 Contract 建立同源会话响应，覆盖实际消费者语义。 */
function ready(overrides: Partial<ContentMediaPlaybackResponse> = {}): ContentMediaPlaybackResponse {
  return {
    content_id: contentId,
    position: 0,
    status: 'ready',
    generation: 1,
    source_revision: firstRevision,
    stream_url: `/api/v1/contents/${contentId}/media/0/playback/stream?session=fixture`,
    job_id: null,
    cooldown_until: null,
    failure_code: null,
    ...overrides,
  }
}

beforeEach(() => { vi.useFakeTimers(); vi.resetAllMocks() })
afterEach(() => { vi.useRealTimers() })

describe('小红书显式视频准备生命周期', () => {
  it('普通用户可读取现有视频，原生失败不发送管理员恢复请求', async () => {
    vi.mocked(prepareMediaPlayback).mockResolvedValue(ready())
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), vi.fn(), () => false)
    await playback.start()
    await playback.mediaError(2)
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(1)
    expect(playback.status.value).toBe('unavailable')
    expect(playback.message.value).toContain('原帖')
    expect(playback.message.value).not.toContain('恢复')
    playback.reset()
  })
  it('初始不请求，重复点击只准备一次，ready 不读取二进制流', async () => {
    vi.mocked(prepareMediaPlayback).mockResolvedValue(ready())
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), vi.fn(), () => true)
    expect(prepareMediaPlayback).not.toHaveBeenCalled()
    await Promise.all([playback.start(), playback.start()])
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(1)
    expect(playback.status.value).toBe('ready')
    expect(playback.streamUrl.value).toContain('/playback/stream?session=fixture')
    playback.reset()
  })

  it('失效只携带上次 ready 代次恢复一次，再失败保留原帖退路', async () => {
    vi.mocked(prepareMediaPlayback).mockResolvedValueOnce(ready()).mockResolvedValueOnce(ready({ source_revision: secondRevision, generation: 2 }))
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), vi.fn(), () => true)
    await playback.start()
    await playback.mediaError(2)
    expect(prepareMediaPlayback).toHaveBeenNthCalledWith(2, contentId, 0, { failed_source_revision: firstRevision }, expect.any(AbortSignal))
    expect(playback.status.value).toBe('ready')
    await playback.mediaError(2)
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(2)
    expect(playback.status.value).toBe('unavailable')
    expect(playback.message.value).toContain('原帖')
    playback.reset()
  })

  it('原生code4由服务器可信失败分类，同代次返回停止且不循环付费刷新', async () => {
    vi.mocked(prepareMediaPlayback).mockResolvedValueOnce(ready()).mockResolvedValueOnce(ready({ failure_code: 'unsupported_format' }))
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), vi.fn(), () => true)
    await playback.start()
    await playback.mediaError(4)
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(2)
    expect(prepareMediaPlayback).toHaveBeenLastCalledWith(contentId, 0, { failed_source_revision: firstRevision }, expect.any(AbortSignal))
    expect(playback.message.value).toContain('不支持此视频格式')
    expect(playback.streamUrl.value).toBeNull()
    await playback.mediaError(4)
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(2)
  })

  it('HTTP403也可能表现为code4，新代次可继续播放而不误报格式', async () => {
    vi.mocked(prepareMediaPlayback).mockResolvedValueOnce(ready()).mockResolvedValueOnce(ready({ source_revision: secondRevision, generation: 2 }))
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), vi.fn(), () => true)
    await playback.start()
    await playback.mediaError(4)
    expect(playback.status.value).toBe('ready')
    expect(playback.message.value).not.toContain('不支持')
    playback.reset()
  })

  it('没有可信失败的同代次无法播放只提示可能原因，不断言已删除或格式', async () => {
    vi.mocked(prepareMediaPlayback).mockResolvedValue(ready())
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), vi.fn(), () => true)
    await playback.start()
    await playback.mediaError(4)
    expect(playback.status.value).toBe('unavailable')
    expect(playback.message.value).toContain('可能')
    expect(playback.message.value).not.toContain('已删除')
  })

  it('只读观察固定准备Job直至ready，缺地址准备已计一次恢复', async () => {
    vi.mocked(prepareMediaPlayback)
      .mockResolvedValueOnce(ready({ status: 'preparing', stream_url: null, job_id: jobId }))
      .mockResolvedValueOnce(ready({ status: 'preparing', stream_url: null, job_id: jobId }))
      .mockResolvedValueOnce(ready({ source_revision: secondRevision }))
    const terminal = vi.fn()
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), terminal, () => true)
    await playback.start()
    await vi.advanceTimersByTimeAsync(1000)
    expect(playback.status.value).toBe('preparing')
    expect(prepareMediaPlayback).toHaveBeenNthCalledWith(2, contentId, 0, { observed_job_id: jobId }, expect.any(AbortSignal))
    await vi.advanceTimersByTimeAsync(1000)
    expect(terminal).toHaveBeenCalledTimes(1)
    expect(playback.status.value).toBe('ready')
    expect(prepareMediaPlayback).toHaveBeenNthCalledWith(3, contentId, 0, { observed_job_id: jobId }, expect.any(AbortSignal))
    await playback.mediaError(2)
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(3)
    expect(playback.status.value).toBe('unavailable')
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each(['unavailable', 'cooldown'] as const)('只读观察失败终态%s停止，冷却过期也不再发送空prepare', async (status) => {
    vi.mocked(prepareMediaPlayback)
      .mockResolvedValueOnce(ready({ status: 'preparing', stream_url: null, job_id: jobId }))
      .mockResolvedValueOnce(ready({ status, stream_url: null, failure_code: 'provider_failed', cooldown_until: '2026-10-09T20:00:00+08:00' }))
    const terminal = vi.fn()
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), terminal, () => true)
    await playback.start()
    await vi.advanceTimersByTimeAsync(120_000)
    expect(playback.status.value).toBe(status)
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(2)
    expect(prepareMediaPlayback).toHaveBeenLastCalledWith(contentId, 0, { observed_job_id: jobId }, expect.any(AbortSignal))
    expect(terminal).toHaveBeenCalledTimes(1)
    expect(playback.message.value).toContain('原帖')
    expect(vi.getTimerCount()).toBe(0)
  })

  it('关闭终止本地 prepare 请求，迟到 ready 不恢复 src', async () => {
    let resolve: (response: ContentMediaPlaybackResponse) => void = () => {}
    vi.mocked(prepareMediaPlayback).mockImplementation(() => new Promise((done) => { resolve = done }))
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), vi.fn(), () => true)
    const pending = playback.start()
    const signal = vi.mocked(prepareMediaPlayback).mock.calls[0]![3]
    playback.reset()
    resolve(ready())
    await pending
    expect(signal.aborted).toBe(true)
    expect(playback.status.value).toBe('idle')
    expect(playback.streamUrl.value).toBeNull()
  })

  it('关闭清除只读观察，迟到终态不提交且只取消本地连接', async () => {
    let resolve: (response: ContentMediaPlaybackResponse) => void = () => {}
    vi.mocked(prepareMediaPlayback)
      .mockResolvedValueOnce(ready({ status: 'preparing', stream_url: null, job_id: jobId }))
      .mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    const terminal = vi.fn()
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), terminal, () => true)
    await playback.start()
    await vi.advanceTimersByTimeAsync(1000)
    expect(prepareMediaPlayback).toHaveBeenLastCalledWith(contentId, 0, { observed_job_id: jobId }, expect.any(AbortSignal))
    const signal = vi.mocked(prepareMediaPlayback).mock.calls[1]![3]
    playback.reset()
    resolve(ready())
    await vi.advanceTimersByTimeAsync(5000)
    expect(signal.aborted).toBe(true)
    expect(terminal).not.toHaveBeenCalled()
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(2)
    expect(playback.status.value).toBe('idle')
    expect(playback.streamUrl.value).toBeNull()
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each([null, '10000000-0000-4000-8000-000000000002'])('只读观察preparing换绑%s时停止，不跟随另一个Job', async (nextJobId) => {
    vi.mocked(prepareMediaPlayback)
      .mockResolvedValueOnce(ready({ status: 'preparing', stream_url: null, job_id: jobId }))
      .mockResolvedValueOnce(ready({ status: 'preparing', stream_url: null, job_id: nextJobId }))
    const terminal = vi.fn()
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), terminal, () => true)
    await playback.start()
    await vi.advanceTimersByTimeAsync(120_000)
    expect(playback.status.value).toBe('unavailable')
    expect(playback.streamUrl.value).toBeNull()
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(2)
    expect(prepareMediaPlayback).toHaveBeenLastCalledWith(contentId, 0, { observed_job_id: jobId }, expect.any(AbortSignal))
    expect(terminal).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('只读观察90秒到期停止本地等待，不无限轮询或自动付费重开', async () => {
    vi.mocked(prepareMediaPlayback).mockResolvedValue(ready({ status: 'preparing', stream_url: null, job_id: jobId }))
    const terminal = vi.fn()
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), terminal, () => true)
    await playback.start()
    const signal = vi.mocked(prepareMediaPlayback).mock.calls[0]![3]
    await vi.advanceTimersByTimeAsync(89_999)
    expect(playback.status.value).toBe('preparing')
    await vi.advanceTimersByTimeAsync(1)
    expect(playback.status.value).toBe('unavailable')
    expect(playback.message.value).toContain('等待超时')
    expect(signal.aborted).toBe(true)
    const requests = vi.mocked(prepareMediaPlayback).mock.calls
    expect(requests).toHaveLength(90)
    expect(requests.slice(1).every((call) => call[2].observed_job_id === jobId && !call[2].failed_source_revision)).toBe(true)
    await vi.advanceTimersByTimeAsync(120_000)
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(90)
    expect(terminal).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('只读观察挂起HTTP也受90秒约束，迟到ready不提交到超时或新播放周期', async () => {
    let resolve: (response: ContentMediaPlaybackResponse) => void = () => {}
    vi.mocked(prepareMediaPlayback)
      .mockResolvedValueOnce(ready({ status: 'preparing', stream_url: null, job_id: jobId }))
      .mockImplementationOnce(() => new Promise((done) => { resolve = done }))
      .mockResolvedValueOnce(ready({ source_revision: secondRevision }))
    const terminal = vi.fn()
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), terminal, () => true)
    await playback.start()
    await vi.advanceTimersByTimeAsync(1000)
    const signal = vi.mocked(prepareMediaPlayback).mock.calls[1]![3]
    await vi.advanceTimersByTimeAsync(89_000)
    expect(playback.status.value).toBe('unavailable')
    expect(signal.aborted).toBe(true)
    await playback.start()
    expect(playback.status.value).toBe('ready')
    resolve(ready({ stream_url: `/api/v1/contents/${contentId}/media/0/playback/stream?session=late` }))
    await vi.advanceTimersByTimeAsync(5000)
    expect(playback.streamUrl.value).not.toContain('session=late')
    expect(terminal).not.toHaveBeenCalled()
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(3)
    expect(vi.getTimerCount()).toBe(0)
    playback.reset()
  })

  it('拒绝远端流地址与错帖会话，签名CDN不会进入播放器', async () => {
    vi.mocked(prepareMediaPlayback).mockResolvedValueOnce(ready({ stream_url: 'https://cdn.example/video?signature=private' }))
    const playback = createMediaPlayback(() => ({ contentId, position: 0 }), vi.fn(), () => true)
    await playback.start()
    expect(playback.status.value).toBe('unavailable')
    expect(playback.streamUrl.value).toBeNull()
    expect(playback.message.value).not.toContain('signature')
    vi.mocked(prepareMediaPlayback).mockResolvedValueOnce(ready({ content_id: 'other' }))
    await playback.start()
    expect(playback.status.value).toBe('unavailable')
  })

  it('失败原因保留格式、仅封面、平台拒绝与删除的用户语义', () => {
    expect(mediaPlaybackMessage('cover_only')).toContain('仅有视频封面')
    expect(mediaPlaybackMessage('cdn_forbidden')).toContain('平台暂时拒绝')
    expect(mediaPlaybackMessage('cdn_gone')).toContain('已删除')
    expect(mediaPlaybackMessage('cdn_not_found')).toContain('已失效')
    expect(mediaPlaybackMessage('unsupported_format')).toContain('格式')
  })
})
