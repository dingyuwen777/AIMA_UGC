<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  description?: string
  mark?: string
}>(), {
  description: '',
  mark: '—',
})
</script>

<template>
  <div class="aima-empty-state">
    <div
      class="empty-mark"
      aria-hidden="true"
    >
      {{ mark }}
    </div>
    <div class="empty-copy">
      <strong>{{ title }}</strong>
      <span v-if="description">{{ description }}</span>
    </div>
    <div
      v-if="$slots.action"
      class="empty-action"
    >
      <slot name="action" />
    </div>
  </div>
</template>

<style scoped>
.aima-empty-state {
  display: flex;
  min-height: 118px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 32px 16px;
  border: 1px solid var(--aima-color-border-default);
  border-radius: var(--aima-radius-lg);
  background: var(--aima-color-bg-white);
  text-align: center;
}
.empty-mark {
  display: grid;
  min-width: 40px;
  height: 40px;
  place-items: center;
  border-radius: var(--aima-radius-full);
  color: var(--aima-color-text-secondary);
  background: var(--aima-color-bg-subtle);
  font-size: 18px;
  font-weight: 700;
  line-height: 26px;
}
.empty-copy { display: grid; gap: 6px; }
.empty-copy strong { color: var(--aima-color-text-primary); font-size: 16px; font-weight: 500; line-height: 24px; }
.empty-copy span { color: var(--aima-color-text-secondary); font-size: 12px; line-height: 18px; }
.empty-action { display: flex; justify-content: center; }
</style>
