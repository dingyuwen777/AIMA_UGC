<script setup lang="ts">
import { ref, watch } from 'vue'

import type {
  KeywordPackResponse,
  KeywordPackSummaryResponse,
  ResourceLifecycleResponse,
} from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import { COLLECTION_PLATFORM_OPTIONS } from '../../../presentation'

const props = defineProps<{
  packs: KeywordPackSummaryResponse[]
  selected: KeywordPackResponse | null
  archived: ResourceLifecycleResponse[]
  total: number
  offset: number
  limit: number
  loading: boolean
  loadingArchived: boolean
  saving: boolean
  toggleReason: (pack: KeywordPackSummaryResponse) => string | null
}>()

const emit = defineEmits<{
  create: []
  edit: []
  open: [packId: string]
  toggle: [pack: KeywordPackSummaryResponse]
  copy: [name: string, onSaved: () => void]
  archive: []
  loadArchived: []
  restoreArchived: [packId: string]
  deleteArchived: [packId: string]
  previous: []
  next: []
}>()

const copyName = ref('')
const copyEditing = ref(false)
const archivedOpen = ref(false)

watch(
  () => props.selected?.id,
  () => {
    copyName.value = ''
    copyEditing.value = false
  },
)

/** 把关键词平台范围转换为当前 Feature 的统一展示文案；全平台范围省略冗余标签。 */
function keywordScopeLabel(scope?: string): string {
  if (!scope || scope === 'all') return ''
  return COLLECTION_PLATFORM_OPTIONS.find((item) => item.value === scope)?.label ?? '指定平台'
}

function copySelected(): void {
  if (!props.selected || !copyName.value.trim()) return
  emit('copy', copyName.value.trim(), () => { copyEditing.value = false })
}

function archiveSelected(): void {
  if (!props.selected) return
  if (!window.confirm(`确认归档词包“${props.selected.name}”吗？归档后不会再出现在当前选择目录，历史任务的冻结配置不会改变。`)) return
  emit('archive')
}

function toggleArchived(open: boolean): void {
  archivedOpen.value = open
  if (open) emit('loadArchived')
}

function onArchivedToggle(event: Event): void {
  toggleArchived((event.currentTarget as HTMLDetailsElement).open)
}

function deleteArchived(item: ResourceLifecycleResponse): void {
  if (!window.confirm(`确认永久删除已归档词包“${item.name}”吗？只有从未产生业务引用的资源才会被服务端允许删除。`)) return
  emit('deleteArchived', item.id)
}
</script>

<template>
  <section class="panel-grid">
    <div class="list-column">
      <div class="table-card">
        <div class="table-head">
          <strong>关键词包</strong><span class="table-head-actions"><span>共 {{ total }} 个</span><AimaButton
            variant="primary"
            size="small"
            icon="plus"
            @click="emit('create')"
          >
            新建词包
          </AimaButton></span>
        </div>
        <div
          v-if="loading"
          class="state"
        >
          正在读取关键词包…
        </div>
        <div
          v-else-if="packs.length === 0"
          class="state"
        >
          暂无关键词包，请先新建。
        </div>
        <div
          v-for="pack in packs"
          v-else
          :key="pack.id"
          class="pack-row"
          :class="{ active: selected?.id === pack.id }"
          role="button"
          tabindex="0"
          :aria-disabled="saving"
          @click="!saving && emit('open', pack.id)"
          @keydown.enter="!saving && emit('open', pack.id)"
          @keydown.space.prevent="!saving && emit('open', pack.id)"
        >
          <span><strong>{{ pack.name }}</strong><small>{{ pack.description || '暂无描述' }}</small></span>
          <span class="count">{{ pack.keyword_count }} 词</span><span>v{{ pack.version }}</span>
          <span :class="['status', pack.enabled ? 'enabled' : 'disabled']">{{ pack.enabled ? '已启用' : '已停用' }}</span>
          <button
            type="button"
            class="link-button"
            :disabled="saving || !!toggleReason(pack)"
            :title="toggleReason(pack) || undefined"
            @click.stop="emit('toggle', pack)"
          >
            {{ pack.enabled ? '停用' : '启用' }}
          </button>
        </div>
      </div>
      <nav
        v-if="total > 0"
        class="pagination"
        aria-label="关键词包分页"
      >
        <span>第 {{ Math.floor(offset / limit) + 1 }} / {{ Math.ceil(total / limit) }} 页 · 每页 {{ limit }} 个</span><span class="pager-actions"><AimaButton
          size="small"
          :disabled="loading || offset === 0"
          @click="emit('previous')"
        >
          上一页
        </AimaButton><AimaButton
          size="small"
          :disabled="loading || offset + limit >= total"
          @click="emit('next')"
        >
          下一页
        </AimaButton></span>
      </nav>

      <details
        class="archived-card"
        :open="archivedOpen"
        @toggle="onArchivedToggle"
      >
        <summary>已归档词包</summary>
        <div
          v-if="loadingArchived"
          class="archived-state"
        >
          正在读取…
        </div>
        <div
          v-else-if="archived.length === 0"
          class="archived-state"
        >
          暂无已归档词包。
        </div>
        <div
          v-for="item in archived"
          v-else
          :key="item.id"
          class="archived-row"
        >
          <span><strong>{{ item.name }}</strong><small>归档于 {{ new Date(item.archived_at).toLocaleString('zh-CN') }}</small></span>
          <AimaButton
            variant="text"
            size="small"
            :disabled="saving"
            @click="emit('restoreArchived', item.id)"
          >
            恢复
          </AimaButton>
          <AimaButton
            variant="text"
            size="small"
            :disabled="saving"
            @click="deleteArchived(item)"
          >
            永久删除
          </AimaButton>
        </div>
      </details>
    </div>

    <aside class="detail-card">
      <template v-if="selected">
        <div class="detail-title">
          <div><span>词包详情</span><strong>{{ selected.name }}</strong></div><span class="version">v{{ selected.version }}</span>
        </div>
        <p>{{ selected.description || '暂无描述' }}</p>

        <div class="resource-actions">
          <AimaButton
            size="small"
            :disabled="saving"
            @click="emit('edit')"
          >
            编辑
          </AimaButton>
          <AimaButton
            size="small"
            :disabled="saving"
            @click="copyName = `${selected.name} 副本`; copyEditing = true"
          >
            复制
          </AimaButton>
          <AimaButton
            size="small"
            :disabled="saving"
            @click="archiveSelected"
          >
            归档
          </AimaButton>
        </div>

        <div
          v-if="copyEditing"
          class="inline-editor"
        >
          <label><span>副本名称</span><input
            v-model="copyName"
            :disabled="saving"
            maxlength="200"
          ></label>
          <small>副本创建后默认停用，不会自动进入采集任务。</small>
          <div>
            <AimaButton
              size="small"
              :disabled="saving"
              @click="copyEditing = false"
            >
              取消
            </AimaButton><AimaButton
              variant="primary"
              size="small"
              :disabled="saving || !copyName.trim()"
              @click="copySelected"
            >
              创建副本
            </AimaButton>
          </div>
        </div>

        <div class="keyword-list">
          <div
            v-for="item in selected.keywords"
            :key="`${item.id}-${item.platform_scope}`"
            class="keyword-row"
          >
            <span><b>{{ item.text }}</b><small v-if="keywordScopeLabel(item.platform_scope)">{{ keywordScopeLabel(item.platform_scope) }}</small></span>
          </div>
          <em v-if="selected.keywords.length === 0">当前词包还没有关键词。</em>
        </div>
      </template>
      <div
        v-else
        class="state"
      >
        选择左侧词包查看关键词明细。
      </div>
    </aside>
  </section>
</template>

<style scoped>
.panel-grid { display: grid; grid-template-columns: minmax(0, 1fr) 373px; gap: 16px; }
.list-column { min-width: 0; }
.table-card,.detail-card,.archived-card { border: 1px solid var(--aima-border); border-radius: 9px; background: #fff; }
.table-head { display: flex; height: 54px; align-items: center; justify-content: space-between; padding: 0 24px 0 18px; border-bottom: 1px solid var(--aima-border); }
.table-head > strong { color: var(--aima-text); font-size: 16px; font-weight: 600; }
.table-head-actions { display: flex; align-items: center; gap: 16px; }.table-head-actions > span { color: #758094; font-size: 12px; }.table-head-actions :deep(.aima-button) { min-width: 92px; height: 32px; }
.pack-row { display: grid; width: 100%; min-height: 74px; grid-template-columns: 1fr 55px 45px 70px 32px; align-items: center; gap: 10px; padding: 15px 18px; border: 0; border-bottom: 1px solid #edf0f4; color: #4e596d; background: #fff; text-align: left; cursor: pointer; }
.pack-row.active { background: #fff7fa; box-shadow: inset 3px 0 var(--aima-primary); }
.pack-row strong,.pack-row small { display: block; }.pack-row strong { color: #1e2838; line-height: 20px; }.pack-row small { margin-top: 5px; color: #818b9d; line-height: 16px; }
.status { width: max-content; padding: 4px 8px; border-radius: 5px; font-size: 12px; }.enabled { color: #118852; background: #eaf8f1; }.disabled { color: #687386; background: #eef1f5; }
.link-button { padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; }.link-button:disabled { color: #98a1b1; cursor: not-allowed; opacity: .75; }
.detail-card { padding: 18px; }.detail-title { display: flex; justify-content: space-between; }.detail-title span,.detail-title strong { display: block; }.detail-title span { color: #7b8598; font-size: 12px; }.detail-title strong { margin-top: 5px; color: var(--aima-text); font-size: 14px; }.version { color: var(--aima-primary) !important; }.detail-card > p { color: #758094; font-size: 12px; }
.resource-actions { display: flex; flex-wrap: wrap; gap: 6px; margin: 14px 0; }
.inline-editor { display: grid; gap: 9px; margin: 12px 0; padding: 10px; border: 1px solid var(--aima-border); border-radius: 7px; background: #fafbfc; }.inline-editor label { display: grid; gap: 5px; color: #6d788a; font-size: 11px; }.inline-editor input,.inline-editor textarea { width: 100%; padding: 7px 9px; border: 1px solid #dce1e9; border-radius: 6px; font: inherit; }.inline-editor > div { display: flex; justify-content: flex-end; gap: 7px; }.inline-editor small { color: #7c8798; font-size: 11px; }
.keyword-list { display: grid; gap: 6px; max-height: 290px; overflow: auto; margin: 14px 0; }.keyword-row { display: flex; min-height: 38px; align-items: center; justify-content: space-between; gap: 10px; padding: 7px 9px; border: 1px solid #dce4f0; border-radius: 6px; background: #f8faff; }.keyword-row > span:first-child { min-width: 0; }.keyword-row b { color: #344258; font-size: 12px; font-weight: 500; }.keyword-row small { margin-left: 5px; color: #8993a3; }.keyword-actions { display: flex; gap: 7px; }.keyword-actions button { padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 11px; }.keyword-actions button:disabled { color: #a0a8b5; cursor: not-allowed; }.keyword-list em { color: #929aaa; font-style: normal; }
.state { display: grid; min-height: 190px; place-items: center; color: #8a93a3; }.pagination { display: flex; min-height: 46px; align-items: center; justify-content: space-between; gap: 10px; padding: 7px 18px; color: #6f7a8d; font-size: 12px; }.pager-actions { display: flex; gap: 34px; }
.archived-card { margin-top: 12px; overflow: hidden; }.archived-card summary { padding: 12px 16px; cursor: pointer; color: #536075; font-size: 12px; font-weight: 600; }.archived-state { padding: 16px; color: #8892a2; font-size: 12px; }.archived-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 8px; padding: 10px 16px; border-top: 1px solid #edf0f4; }.archived-row strong,.archived-row small { display: block; }.archived-row strong { color: #313c4f; font-size: 12px; }.archived-row small { margin-top: 3px; color: #929baa; font-size: 10px; }
.pack-row > span:first-child,.detail-title > div { min-width: 0; overflow-wrap: anywhere; }
.detail-card > p,.keyword-row b,.archived-row strong { overflow-wrap: anywhere; }
.keyword-actions { flex: none; white-space: nowrap; }
@media (max-width: 1260px) { .panel-grid { grid-template-columns: minmax(0, 1fr); gap: 24px; }.detail-card { width: min(100%, 373px); min-height: 260px; } }
</style>
