<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import type { ContentMediaResponse } from '../../../../../generated/api/client'
import { createMediaPlayback } from '../../../mediaPlayback'

const props = defineProps<{
  contentId: string
  media: ContentMediaResponse
  originalUrl?: string | null
  active: boolean
}>()
const emit = defineEmits<{ terminal: [] }>()
const video = ref<HTMLVideoElement | null>(null)
const coverFailed = ref(false)
const playback = createMediaPlayback(
  () => ({ contentId: props.contentId, position: props.media.position }),
  () => emit('terminal'),
)
const { status, streamUrl, message, cooldownUntil } = playback
const duration = computed(() => {
  const milliseconds = props.media.duration_ms
  if (milliseconds == null || !Number.isFinite(milliseconds) || milliseconds < 0) return null
  const seconds = Math.floor(milliseconds / 1000)
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
})

/** 释放原生媒体连接与缓冲；本地关闭不取消服务器共享准备任务。 */
function releaseVideo(): void {
  const element = video.value
  if (!element) return
  element.pause()
  element.removeAttribute('src')
  element.load()
}

/** 当前原生播放失败交给同一准备状态机，恢复次数不会随重新渲染重置。 */
function onMediaError(): void {
  const code = video.value?.error?.code
  releaseVideo()
  void playback.mediaError(code)
}

/** 关闭、切帖与切换媒体都使迟到请求失效，并主动释放浏览器连接。 */
watch(() => [props.contentId, props.media.position, props.active] as const, () => {
  releaseVideo()
  playback.reset()
}, { flush: 'sync' })
watch(() => props.media.preview_url, () => { coverFailed.value = false })
onBeforeUnmount(() => {
  releaseVideo()
  playback.reset()
})
</script>

<template>
  <div
    class="content-video"
    aria-label="小红书视频"
  >
    <div class="video-stage">
      <video
        v-if="active && streamUrl"
        ref="video"
        :src="streamUrl"
        :poster="!coverFailed ? media.preview_url || undefined : undefined"
        controls
        playsinline
        preload="none"
        aria-label="内容视频播放器"
        @error="onMediaError"
      />
      <template v-else>
        <img
          v-if="media.preview_url && !coverFailed"
          :src="media.preview_url"
          :alt="media.alt_text || '视频封面'"
          @error="coverFailed = true"
        >
        <span
          v-else
          class="video-placeholder"
        >暂无视频封面</span>
        <button
          class="video-prepare"
          type="button"
          :disabled="status === 'preparing' || !active"
          :aria-label="status === 'preparing' ? '正在准备视频' : '准备播放视频'"
          @click="playback.start"
        >
          {{ status === 'preparing' ? '正在准备…' : status === 'idle' ? '准备播放视频' : '重新准备视频' }}
        </button>
      </template>
      <span class="video-kind">视频<template v-if="duration"> · {{ duration }}</template></span>
    </div>
    <p
      class="video-status"
      role="status"
      aria-live="polite"
    >
      {{ message || '点击后准备视频，准备完成后可使用播放器播放。' }}
      <span v-if="cooldownUntil">请稍后再试。</span>
      <span v-if="status === 'unavailable' || status === 'cooldown'">已保留已入库内容。</span>
    </p>
    <a
      v-if="originalUrl"
      :href="originalUrl"
      target="_blank"
      rel="noopener noreferrer"
    >前往原帖查看 ↗</a>
  </div>
</template>

<style scoped>
.content-video { display: grid; min-width: 0; gap: 8px; }
.video-stage { position: relative; display: grid; grid-template: minmax(0, 1fr) / minmax(0, 1fr); width: 100%; height: clamp(200px, 48dvh, 440px); min-width: 0; place-items: center; overflow: hidden; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-xl); background: var(--aima-surface-subtle); }
.video-stage img, .video-stage video { display: block; width: 100%; height: 100%; max-width: 100%; max-height: 100%; object-fit: contain; }
.video-stage video { background: #111625; }
.video-placeholder { color: var(--aima-text-disabled); font-size: 13px; }
.video-prepare { position: absolute; top: 50%; left: 50%; max-width: calc(100% - 32px); padding: 10px 16px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-full); color: var(--aima-text); background: rgb(255 255 255 / 94%); cursor: pointer; transform: translate(-50%, -50%); }
.video-prepare:disabled { cursor: wait; opacity: .8; }
.video-prepare:focus-visible { outline: 2px solid var(--aima-primary); outline-offset: 3px; }
.video-kind { position: absolute; top: 10px; left: 10px; padding: 4px 8px; border-radius: 6px; color: white; background: rgb(17 22 37 / 75%); font-size: 12px; pointer-events: none; }
.video-status { margin: 0; color: var(--aima-text-muted); font-size: 12px; line-height: 20px; overflow-wrap: anywhere; }
.content-video > a { justify-self: start; color: var(--aima-primary); font-size: 12px; }
@media (max-width: 600px) { .video-stage { height: clamp(180px, 42dvh, 360px); } }
</style>
