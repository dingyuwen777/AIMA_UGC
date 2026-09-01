<script setup lang="ts">
export type AimaIconName =
  | 'home'
  | 'voice'
  | 'runtime'
  | 'strategy'
  | 'settings'
  | 'refresh'
  | 'plus'
  | 'search'
  | 'info'
  | 'warning'
  | 'success'
  | 'close'
  | 'copy'
  | 'ai'
  | 'download'
  | 'empty'

withDefaults(defineProps<{
  name: AimaIconName
  size?: number
}>(), { size: 18 })
</script>

<template>
  <svg
    :data-aima-icon="name"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <template v-if="name === 'home'">
      <path d="M3 11.5 12 4l9 7.5" /><path d="M5.5 10.5V20h13v-9.5" /><path d="M9.5 20v-6h5v6" />
    </template>
    <template v-else-if="name === 'voice'">
      <path d="M4 13.5v-3M8 17V7M12 20V4M16 17V7M20 13.5v-3" />
    </template>
    <template v-else-if="name === 'runtime'">
      <rect
        x="3.5"
        y="4"
        width="17"
        height="16"
        rx="2"
      /><path d="M8 2v4M16 2v4M3.5 9h17" /><path d="m9 14 2 2 4-4" />
    </template>
    <template v-else-if="name === 'strategy'">
      <circle
        cx="12"
        cy="12"
        r="8.5"
      /><circle
        cx="12"
        cy="12"
        r="4.5"
      /><circle
        cx="12"
        cy="12"
        r="1"
        fill="currentColor"
        stroke="none"
      />
    </template>
    <template v-else-if="name === 'settings'">
      <circle
        cx="12"
        cy="12"
        r="3"
      /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4v-.2a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
    </template>
    <template v-else-if="name === 'refresh'">
      <path d="M20 7v5h-5" /><path d="M18.4 15A7.5 7.5 0 1 1 19 8.1L20 12" />
    </template>
    <template v-else-if="name === 'plus'">
      <path d="M12 5v14M5 12h14" />
    </template>
    <template v-else-if="name === 'search'">
      <circle
        cx="10.5"
        cy="10.5"
        r="6.5"
      /><path d="m15.5 15.5 4 4" />
    </template>
    <template v-else-if="name === 'info'">
      <circle
        cx="12"
        cy="12"
        r="9"
      /><path d="M12 10.5V17" /><path d="M12 7h.01" />
    </template>
    <template v-else-if="name === 'warning'">
      <path d="M12 3.5 21 20H3L12 3.5Z" /><path d="M12 9v5" /><path d="M12 17h.01" />
    </template>
    <template v-else-if="name === 'success'">
      <circle
        cx="12"
        cy="12"
        r="9"
      /><path d="m8 12 2.6 2.6L16.5 9" />
    </template>
    <template v-else-if="name === 'close'">
      <path d="m6 6 12 12M18 6 6 18" />
    </template>
    <template v-else-if="name === 'copy'">
      <rect
        x="8"
        y="8"
        width="11"
        height="11"
        rx="2"
      /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
    </template>
    <template v-else-if="name === 'ai'">
      <path d="m12 3 1.45 3.55L17 8l-3.55 1.45L12 13l-1.45-3.55L7 8l3.55-1.45L12 3Z" />
      <path d="m18.5 14 .75 1.75L21 16.5l-1.75.75L18.5 19l-.75-1.75L16 16.5l1.75-.75.75-1.75Z" />
    </template>
    <template v-else-if="name === 'download'">
      <path d="M12 3v11" /><path d="m8 10 4 4 4-4" /><path d="M5 19h14" />
    </template>
    <template v-else-if="name === 'empty'">
      <path d="m12 5 7 7-7 7-7-7 7-7Z" />
    </template>
  </svg>
</template>
