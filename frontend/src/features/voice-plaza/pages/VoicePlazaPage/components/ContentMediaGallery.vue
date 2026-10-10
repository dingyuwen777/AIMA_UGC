<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import type { ContentMediaResponse } from '../../../../../generated/api/client'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import ContentVideoPlayer from './ContentVideoPlayer.vue'

const props = defineProps<{
  contentId: string
  platform: string
  media: ContentMediaResponse[]
  contentType: string
  originalUrl?: string | null
  open: boolean
  canRecover: boolean
}>()
const emit = defineEmits<{ terminal: [] }>()
const grid = ref<HTMLElement | null>(null)
const activeIndex = ref(0)
const xiaohongshu = computed(() => props.platform === 'xiaohongshu')
const hasVideo = computed(() => props.contentType === 'video' || props.media.some((item) => item.media_type === 'video'))
const navigation = computed(() => xiaohongshu.value && props.media.length > 1)
const onlyImages = computed(() => props.media.every((item) => item.media_type === 'image'))

/** 以实际卡片位置滚动，保持横竖图尺寸不影响页码与按钮状态。 */
function show(index: number): void {
  const element = grid.value
  if (!element) return
  const next = Math.max(0, Math.min(props.media.length - 1, index))
  const target = element.children.item(next)
  if (!(target instanceof HTMLElement)) return
  activeIndex.value = next
  element.scrollTo({ left: element.scrollLeft + target.getBoundingClientRect().left - element.getBoundingClientRect().left, behavior: 'auto' })
}

/** 原生触控或触控板滚动仍以最近的卡片同步页码。 */
function syncIndex(): void {
  const element = grid.value
  if (!element || !navigation.value) return
  const left = element.getBoundingClientRect().left
  let closest = 0
  let distance = Infinity
  Array.from(element.children).forEach((child, index) => {
    const current = Math.abs(child.getBoundingClientRect().left - left)
    if (current < distance) { distance = current; closest = index }
  })
  activeIndex.value = closest
}

/** 切帖或关闭重置本地画廊，后台同帖更新保留阅读与播放位置。 */
watch(() => [props.contentId, props.open] as const, async () => {
  activeIndex.value = 0
  await nextTick()
  if (grid.value) grid.value.scrollLeft = 0
})

/** 同帖刷新按媒体身份保留选中项；已移除时归一到仍有效的位置，单媒体也必须激活。 */
watch(() => [props.contentId, props.media.map((entry) => `${entry.position}:${entry.media_type}`)] as const, async ([contentId, next], [previousContentId, previous]) => {
  if (contentId !== previousContentId || (next.length === previous.length && next.every((key, index) => key === previous[index]))) return
  const selected = previous[activeIndex.value]
  const preserved = selected ? next.indexOf(selected) : -1
  activeIndex.value = preserved >= 0 ? preserved : Math.max(0, Math.min(activeIndex.value, next.length - 1))
  await nextTick()
  show(activeIndex.value)
})
</script>

<template>
  <section
    class="content-media"
    aria-label="内容媒体"
  >
    <div
      v-if="xiaohongshu"
      class="media-heading"
    >
      <strong>{{ hasVideo ? '视频' : '图片' }}</strong><small v-if="onlyImages">点击图片查看完整原图</small>
    </div>
    <div
      class="media-carousel"
      :class="{ 'media-carousel--contained': xiaohongshu }"
    >
      <div
        ref="grid"
        class="media-grid"
        :class="{ 'media-grid--contained': xiaohongshu, 'media-grid--carousel': navigation }"
        @scroll.passive="syncIndex"
      >
        <template
          v-for="(entry, index) in props.media"
          :key="`${contentId}:${entry.position}`"
        >
          <ContentVideoPlayer
            v-if="xiaohongshu && entry.media_type === 'video'"
            :content-id="contentId"
            :media="entry"
            :original-url="originalUrl"
            :active="open && activeIndex === index"
            :can-recover="canRecover"
            @terminal="emit('terminal')"
          />
          <a
            v-else
            :href="xiaohongshu ? (entry.preview_url || entry.url || undefined) : (entry.url || entry.preview_url || undefined)"
            target="_blank"
            rel="noopener noreferrer"
            :aria-label="xiaohongshu ? `查看完整图片 ${index + 1}` : '查看原始媒体'"
          >
            <div class="media-image-stage">
              <img
                v-if="entry.preview_url"
                :src="entry.preview_url"
                :alt="entry.alt_text || '原始内容媒体预览'"
              >
              <span v-else>{{ entry.media_type }} · 查看原始媒体</span>
            </div>
          </a>
        </template>
      </div>
      <template v-if="navigation">
        <button
          class="media-navigation media-navigation--previous"
          type="button"
          :aria-label="onlyImages ? '上一张图片' : '上一个媒体'"
          :disabled="activeIndex === 0"
          @click="show(activeIndex - 1)"
        >
          <AimaIcon
            name="chevron-left"
            :size="20"
          />
        </button>
        <span
          class="media-position"
          aria-live="polite"
          aria-atomic="true"
        >{{ activeIndex + 1 }} / {{ media.length }}</span>
        <button
          class="media-navigation media-navigation--next"
          type="button"
          :aria-label="onlyImages ? '下一张图片' : '下一个媒体'"
          :disabled="activeIndex === media.length - 1"
          @click="show(activeIndex + 1)"
        >
          <AimaIcon
            name="chevron-right"
            :size="20"
          />
        </button>
      </template>
    </div>
  </section>
</template>

<style scoped>
.content-media { min-width: 0; }
.media-heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.media-heading strong { color: var(--aima-text); font-size: 13px; }
.media-heading small { color: var(--aima-text-muted); font-size: 11px; }
.media-carousel { position: relative; min-width: 0; }
.media-grid { display: grid; grid-template-columns: 1fr; gap: 8px; }
.media-grid a { display: grid; min-width: 0; min-height: 78px; place-items: center; overflow: hidden; border-radius: 7px; color: var(--aima-text-muted); background: var(--aima-surface-subtle); font-size: 11px; text-decoration: none; }
.media-image-stage { display: block; width: 100%; min-width: 0; }
.media-image-stage img { display: block; width: 100%; height: 100px; object-fit: cover; }
.media-grid--contained > a { border: 1px solid var(--aima-border); border-radius: var(--aima-radius-xl); }
.media-grid--contained .media-image-stage { height: clamp(200px, 48dvh, 440px); overflow: hidden; }
.media-grid--contained .media-image-stage img { width: 100%; height: 100%; max-width: 100%; max-height: 100%; object-fit: contain; }
.media-grid--contained a:focus-visible { outline: 2px solid var(--aima-primary); outline-offset: -3px; }
.media-grid--carousel { display: grid; grid-auto-flow: column; grid-auto-columns: 100%; grid-template-columns: none; overflow-x: auto; gap: 10px; scroll-snap-type: x mandatory; overscroll-behavior-inline: contain; scrollbar-width: none; }
.media-grid--carousel::-webkit-scrollbar { display: none; }
.media-grid--carousel > * { min-width: 0; scroll-snap-align: start; scroll-snap-stop: always; }
.media-navigation { position: absolute; z-index: 1; top: 50%; display: grid; width: 34px; height: 34px; padding: 0; place-items: center; border: 1px solid var(--aima-border); border-radius: 50%; background: rgb(255 255 255 / 94%); color: var(--aima-text); cursor: pointer; transform: translateY(-50%); }
.media-navigation--previous { left: 10px; }
.media-navigation--next { right: 10px; }
.media-navigation:disabled { cursor: default; opacity: .38; }
.media-navigation:focus-visible { outline: 2px solid var(--aima-primary); outline-offset: 2px; }
.media-position { position: absolute; z-index: 1; right: 10px; bottom: 10px; padding: 4px 8px; border-radius: var(--aima-radius-full); color: white; background: rgb(17 22 37 / 75%); font-size: 11px; pointer-events: none; }
@media (max-width: 600px) { .media-grid--contained .media-image-stage { height: clamp(180px, 42dvh, 360px); } }
</style>
