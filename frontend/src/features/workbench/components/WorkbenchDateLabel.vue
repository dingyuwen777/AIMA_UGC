<script setup lang="ts">
defineProps<{ from: string; to: string }>()
</script>

<template>
  <small
    class="workbench-date-label"
    :title="`${from} — ${to}`"
  >{{ from }} — {{ to }}</small>
</template>

<style scoped>
.workbench-date-label { min-width: 0; overflow: hidden; color: var(--aima-text-disabled); font-size: clamp(10px, 1.4cqw, 12px); text-overflow: ellipsis; white-space: nowrap; }
</style>
