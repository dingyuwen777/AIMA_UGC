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
.aima-page-header {
  display: flex;
  min-width: 0;
  min-height: 64px;
  align-items: center;
  justify-content: space-between;
  gap: var(--aima-density-section-gap);
}

.aima-page-header > div:first-child {
  min-width: 0;
}

h1 {
  margin: 0;
  color: var(--aima-text);
  font-size: var(--aima-font-size-page-title);
  font-weight: 650;
  line-height: var(--aima-line-height-heading);
}

p {
  margin: 3px 0 0;
  color: var(--aima-text-muted);
  font-size: var(--aima-font-size-body-small);
  line-height: var(--aima-line-height-body);
}

.aima-page-actions {
  display: flex;
  flex: none;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 1279px) {
  .aima-page-header {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .aima-page-actions {
    flex: 1 1 100%;
    justify-content: flex-start;
  }
}
</style>