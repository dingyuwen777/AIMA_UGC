<script setup lang="ts">
import AppShell from '../app/layouts/AppShell.vue'
import workbenchPlaceholder from '../assets/workbench-placeholder.png'
</script>

<template>
  <AppShell section-title="工作台">
    <img
      class="workbench-placeholder"
      :src="workbenchPlaceholder"
      alt="工作台开发中"
      width="1078"
      height="722"
    >
  </AppShell>
</template>

<style scoped>
.workbench-placeholder {
  display: block;
  width: 100%;
  height: auto;
}
</style>
