<script setup lang="ts">
import { computed } from 'vue'

import { platformLabel } from '../domain/platform'

const props = defineProps<{ platform: string }>()

const marks: Record<string, string> = {
  xiaohongshu: '书',
  douyin: '抖',
  weibo: '微',
  bilibili: 'B',
  kuaishou: '快',
}
const mark = computed(() => marks[props.platform] ?? platformLabel(props.platform).slice(0, 1))
</script>

<template>
  <span
    class="platform-mark"
    :class="`platform-mark--${platform}`"
    :title="platformLabel(platform)"
    :aria-label="platformLabel(platform)"
  >{{ mark }}</span>
</template>

<style scoped>
.platform-mark { display: grid; min-width: 22px; height: 22px; flex: none; place-items: center; padding-inline: 4px; border-radius: 2px; color: #fff; background: var(--aima-primary); font-size: 12px; font-weight: 700; }
.platform-mark--douyin { background: #0b0d0c; }
.platform-mark--weibo { background: #e8cc94; }
.platform-mark--kuaishou { background: #f97316; }
.platform-mark--bilibili { background: #00a1d6; }
</style>
