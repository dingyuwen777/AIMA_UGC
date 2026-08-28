<script setup lang="ts">
defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <header class="aima-page-header">
    <div>
      <h1>{{ title }}</h1>
      <p>{{ description }}</p>
    </div>
    <div class="aima-page-actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.aima-page-header { display: flex; min-height: 64px; align-items: center; justify-content: space-between; gap: 24px; }
h1 { margin: 0; color: var(--aima-text); font-size: 24px; font-weight: 650; line-height: 32px; }
p { margin: 3px 0 0; color: var(--aima-text-muted); font-size: 12px; line-height: 18px; }
.aima-page-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
</style>
