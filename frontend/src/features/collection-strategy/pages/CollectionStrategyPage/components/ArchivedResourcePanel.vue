<script setup lang="ts">
import { ref } from 'vue'

import type { ResourceLifecycleResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import { formatBeijingDateTime } from '../../../presentation'

defineProps<{
  title: string
  items: ResourceLifecycleResponse[]
  loading: boolean
  saving: boolean
  loadingMessage: string
  emptyMessage: string
}>()

const emit = defineEmits<{
  load: []
  restore: [item: ResourceLifecycleResponse]
  requestDelete: [item: ResourceLifecycleResponse]
}>()

const open = ref(false)

/** 切换低频归档目录；首次展开时由父级按需读取真实归档数据。 */
function toggle(): void {
  open.value = !open.value
  if (open.value) emit('load')
}
</script>

<template>
  <section class="archived-resource">
    <button
      type="button"
      class="archive-toggle"
      :aria-expanded="open"
      @click="toggle"
    >
      <strong>{{ title }}</strong><span>{{ open ? '收起' : '展开' }}</span>
    </button>
    <template v-if="open">
      <div
        v-if="loading"
        class="archive-state"
        role="status"
      >
        {{ loadingMessage }}
      </div>
      <div
        v-else-if="items.length === 0"
        class="archive-state"
      >
        {{ emptyMessage }}
      </div>
      <div
        v-for="item in items"
        v-else
        :key="item.id"
        class="archive-row"
      >
        <span class="archive-summary"><strong>{{ item.name }}</strong><small>归档于 {{ formatBeijingDateTime(item.archived_at) }}</small></span>
        <span class="archive-actions"><AimaButton
          size="small"
          :disabled="saving"
          @click="emit('restore', item)"
        >
          恢复
        </AimaButton><AimaButton
          variant="text"
          size="small"
          :disabled="saving"
          @click="emit('requestDelete', item)"
        >
          永久删除
        </AimaButton></span>
      </div>
    </template>
  </section>
</template>

<style scoped>
.archived-resource { overflow: hidden; border: 1px solid var(--aima-border); border-radius: 8px; background: var(--aima-surface); }
.archive-toggle { display: flex; width: 100%; height: 44px; align-items: center; justify-content: space-between; padding: 0 12px 0 16px; border: 0; color: var(--aima-text); background: var(--aima-surface-subtle); cursor: pointer; text-align: left; }
.archive-toggle strong { font-size: 12px; font-weight: 600; }.archive-toggle span { padding: 4px; color: var(--aima-primary); font-size: 12px; }
.archive-toggle:focus-visible { outline: 2px solid var(--aima-primary-soft-strong); outline-offset: -2px; }
.archive-state { display: flex; min-height: 52px; align-items: center; padding: 8px 16px; border-top: 1px solid var(--aima-border); color: var(--aima-text-secondary); font-size: 12px; }
.archive-row { display: flex; min-height: 60px; align-items: center; justify-content: space-between; gap: 16px; padding: 8px 12px 8px 16px; border-top: 1px solid var(--aima-border); }
.archive-summary { min-width: 0; }.archive-summary strong,.archive-summary small { display: block; overflow-wrap: anywhere; }.archive-summary strong { color: var(--aima-text); font-size: 13px; font-weight: 500; line-height: 20px; }.archive-summary small { margin-top: 2px; color: var(--aima-text-secondary); font-size: 11px; line-height: 18px; }
.archive-actions { display: flex; flex: none; align-items: center; gap: 8px; }.archive-actions :deep(.is-text) { color: #657084; }
</style>
