<script setup lang="ts">
import { computed } from 'vue'

import { platformColor, platformLabel } from '../domain/platform'

const props = defineProps<{ platform: string }>()

const marks: Record<string, string> = {
  xiaohongshu: '书',
  douyin: '抖',
  weibo: '微',
  bilibili: 'B',
  kuaishou: '快',
}
const mark = computed(() => marks[props.platform] ?? platformLabel(props.platform).slice(0, 1))
const color = computed(() => platformColor(props.platform))
</script>

<template>
  <span
    class="platform-mark"
    :style="{ background: color }"
    :title="platformLabel(platform)"
    :aria-label="platformLabel(platform)"
  >{{ mark }}</span>
</template>

<style scoped>
.platform-mark { display: grid; min-width: 22px; height: 22px; flex: none; place-items: center; padding-inline: 4px; border-radius: 2px; color: #fff; font-size: 12px; font-weight: 700; }
</style>
