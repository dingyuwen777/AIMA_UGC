<script setup lang="ts">
import { ref } from 'vue'

import type { KeywordPackResponse, KeywordPackSummaryResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import { COLLECTION_PLATFORM_OPTIONS } from '../../../presentation'

defineProps<{
  packs: KeywordPackSummaryResponse[]
  selected: KeywordPackResponse | null
  total: number
  offset: number
  limit: number
  loading: boolean
  saving: boolean
  toggleReason: (pack: KeywordPackSummaryResponse) => string | null
}>()

const emit = defineEmits<{
  create: []
  open: [packId: string]
  toggle: [pack: KeywordPackSummaryResponse]
  addKeyword: [packId: string, text: string]
  previous: []
  next: []
}>()

const keyword = ref('')

/** 把关键词平台范围转换为当前 Feature 的统一展示文案；全平台范围按正式 Figma 省略冗余标签。 */
function keywordScopeLabel(scope?: string): string {
  if (!scope || scope === 'all') return ''
  return COLLECTION_PLATFORM_OPTIONS.find((item) => item.value === scope)?.label ?? scope
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
          @click="emit('open', pack.id)"
          @keydown.enter="emit('open', pack.id)"
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
      </div><nav
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
    </div>

    <aside class="detail-card">
      <template v-if="selected">
        <div class="detail-title">
          <div><span>词包详情</span><strong>{{ selected.name }}</strong></div><span class="version">v{{ selected.version }}</span>
        </div>
        <p>{{ selected.description || '暂无描述' }}</p>
        <div class="keyword-list">
          <span
            v-for="item in selected.keywords"
            :key="`${item.id}-${item.platform_scope}`"
          >{{ item.text }}<small v-if="keywordScopeLabel(item.platform_scope)">{{ keywordScopeLabel(item.platform_scope) }}</small></span>
          <em v-if="selected.keywords.length === 0">当前词包还没有关键词。</em>
        </div>
        <form @submit.prevent="emit('addKeyword', selected.id, keyword.trim()); keyword = ''">
          <input
            v-model="keyword"
            maxlength="500"
            placeholder="新增关键词"
            required
          ><button
            type="submit"
            :disabled="saving || !keyword.trim()"
          >
            添加
          </button>
        </form>
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
.panel-grid { display: grid; grid-template-columns: minmax(620px, 823px) minmax(320px, 373px); gap: 16px; }
.list-column { min-width: 0; }
.table-card,.detail-card { border: 1px solid var(--aima-border); border-radius: 9px; background: #fff; }
.table-head { display: flex; height: 54px; align-items: center; justify-content: space-between; padding: 0 24px 0 18px; border-bottom: 1px solid var(--aima-border); }
.table-head > strong { color: var(--aima-text); font-size: 16px; font-weight: 600; }
.table-head-actions { display: flex; align-items: center; gap: 16px; }.table-head-actions > span { color: #758094; font-size: 12px; }.table-head-actions :deep(.aima-button) { min-width: 92px; height: 32px; }
.pack-row { display: grid; width: 100%; min-height: 74px; grid-template-columns: 1fr 55px 45px 70px 32px; align-items: center; gap: 10px; padding: 15px 18px; border: 0; border-bottom: 1px solid #edf0f4; color: #4e596d; background: #fff; text-align: left; cursor: pointer; }
.pack-row.active { background: #fff7fa; box-shadow: inset 3px 0 var(--aima-primary); }
.pack-row strong,.pack-row small { display: block; }.pack-row strong { color: #1e2838; }.pack-row small { margin-top: 5px; color: #818b9d; }
.status { width: max-content; padding: 4px 8px; border-radius: 5px; font-size: 12px; }.enabled { color: #118852; background: #eaf8f1; }.disabled { color: #687386; background: #eef1f5; }
.link-button { padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; }.link-button:disabled { color: #98a1b1; cursor: not-allowed; opacity: .75; }
.detail-card { padding: 18px; }.detail-title { display: flex; justify-content: space-between; }.detail-title span,.detail-title strong { display: block; }.detail-title span { color: #7b8598; font-size: 12px; }.detail-title strong { margin-top: 5px; color: var(--aima-text); font-size: 14px; }.version { color: var(--aima-primary) !important; }.detail-card p { color: #758094; font-size: 12px; }
.keyword-list { display: flex; max-height: 330px; flex-wrap: wrap; gap: 8px; overflow: auto; margin: 18px 0; }.keyword-list > span { min-height: 33px; padding: 7px 9px; border: 1px solid #dce4f0; border-radius: 6px; color: #344258; background: #f8faff; font-size: 12px; }.keyword-list small { margin-left: 5px; color: #8993a3; }.keyword-list em { color: #929aaa; font-style: normal; }
form { display: flex; width: 287px; margin: 18px auto 0; gap: 12px; }input { min-width: 0; width: 217px; height: 40px; flex: 1; padding: 0 10px; border: 1px solid #dce1e9; border-radius: 6px; }form button { width: 58px; height: 40px; flex: none; border: 0; border-radius: 6px; color: #fff; background: var(--aima-primary); cursor: pointer; }
.state { display: grid; min-height: 190px; place-items: center; color: #8a93a3; }
.pagination { display: flex; min-height: 46px; align-items: center; justify-content: space-between; gap: 10px; padding: 7px 18px; color: #6f7a8d; font-size: 12px; }.pager-actions { display: flex; gap: 34px; }
</style>
