<script setup lang="ts">
import { ref } from 'vue'

import AppShell from '../../../app/layouts/AppShell.vue'
import AimaButton from '../../../shared/ui/AimaButton.vue'
import AimaDialog from '../../../shared/ui/AimaDialog.vue'
import AimaIcon from '../../../shared/ui/AimaIcon.vue'
import AimaPageHeader from '../../../shared/ui/AimaPageHeader.vue'
import ProviderConfigurationPanel from '../components/ProviderConfigurationPanel.vue'
import AnalysisSchemePanel from './AdminConfigurationPage/components/AnalysisSchemePanel.vue'
import AuditPanel from './AdminConfigurationPage/components/AuditPanel.vue'
import CatalogConfigurationPanel from './AdminConfigurationPage/components/CatalogConfigurationPanel.vue'
import ReportStrategyPanel from './AdminConfigurationPage/components/ReportStrategyPanel.vue'

type Tab = 'catalog' | 'llm' | 'tikhub' | 'scheme' | 'audit' | 'report'

const tab = ref<Tab>('catalog')
const currentDirty = ref(false)
const pendingTab = ref<Tab | null>(null)

const tabItems = [
  ['catalog', '品牌与车型'],
  ['llm', 'AI 模型'],
  ['tikhub', 'TikHub'],
  ['scheme', 'AI 分析规则'],
  ['audit', '操作记录'],
  ['report', '报告策略'],
] as const

/** 将机器 Tab 标识映射为用户可见名称。 */
function tabLabel(value: Tab | null): string {
  return tabItems.find(([key]) => key === value)?.[1] ?? ''
}

/** 使用当前编辑对象的业务名称生成未保存提示。 */
function dirtySubject(value: Tab): string {
  if (value === 'catalog') return '品牌与车型配置'
  if (value === 'llm') return 'AI 模型配置'
  if (value === 'tikhub') return 'TikHub 配置'
  if (value === 'scheme') return 'AI 分析规则'
  if (value === 'report') return '报告策略'
  return '当前页面'
}

/** 子 Feature 只上送 dirty 事实，Page Owner 统一决定是否允许离开。 */
function handleDirtyChange(dirty: boolean): void {
  currentDirty.value = dirty
}

/** 请求切换页签；存在未保存输入时先进入正式确认状态。 */
function requestTab(next: Tab): void {
  if (next === tab.value) return
  if (currentDirty.value) {
    pendingTab.value = next
    return
  }
  currentDirty.value = false
  tab.value = next
}

/** 保留当前草稿并关闭离开确认。 */
function continueEditing(): void {
  pendingTab.value = null
}

/** 明确放弃当前草稿后再切换到用户最初选择的目标页签。 */
function discardAndSwitch(): void {
  const next = pendingTab.value
  if (!next) return
  currentDirty.value = false
  pendingTab.value = null
  tab.value = next
}

/**
 * 页面私有组件继续持有原有表单守卫：CatalogConfigurationPanel 使用 vehicleFormValid 与
 * :disabled="saving || !vehicleFormValid"；AnalysisSchemePanel 使用
 * :readonly="selectedSchemeVersion?.version.status === 'draft'"，并保留“编辑现有草稿时名称保持不变”的提示。
 * 主页面只负责组合与 Tab 状态，不复制这些业务校验。
 */
</script>

<template>
  <AppShell section-title="管理员配置">
    <main class="admin-page">
      <AimaPageHeader
        title="管理员配置"
        description="统一管理品牌、车型、AI 模型、采集服务、AI 分析规则和报告发布准备。技术标识与原始审计数据仅在需要时展开查看。"
      />

      <nav
        class="tabs"
        aria-label="管理员配置分类"
      >
        <button
          v-for="item in tabItems"
          :key="item[0]"
          type="button"
          :class="{ active: tab === item[0] }"
          @click="requestTab(item[0])"
        >
          {{ item[1] }}
        </button>
      </nav>

      <CatalogConfigurationPanel
        v-if="tab === 'catalog'"
        @dirty-change="handleDirtyChange"
      />
      <ProviderConfigurationPanel
        v-else-if="tab === 'llm'"
        provider-kind="llm"
        @dirty-change="handleDirtyChange"
      />
      <ProviderConfigurationPanel
        v-else-if="tab === 'tikhub'"
        provider-kind="collection"
        @dirty-change="handleDirtyChange"
      />
      <AnalysisSchemePanel
        v-else-if="tab === 'scheme'"
        @dirty-change="handleDirtyChange"
      />
      <AuditPanel v-else-if="tab === 'audit'" />
      <ReportStrategyPanel
        v-else
        @dirty-change="handleDirtyChange"
      />

      <AimaDialog
        :model-value="pendingTab !== null"
        label="放弃未保存的修改"
        width="480px"
        class="admin-unsaved-dialog"
        @update:model-value="(open) => { if (!open) continueEditing() }"
      >
        <template #header>
          <header class="unsaved-dialog-header">
            <div>
              <h2>放弃未保存的修改？</h2>
              <small>切换页签前确认当前输入如何处理。</small>
            </div>
            <button
              type="button"
              class="unsaved-dialog-close"
              aria-label="关闭未保存修改确认"
              @click="continueEditing"
            >
              <AimaIcon
                name="close"
                :size="20"
              />
            </button>
          </header>
        </template>
        <div class="unsaved-dialog-body">
          <p><strong>{{ dirtySubject(tab) }}</strong>仍有未保存修改。切换到 {{ tabLabel(pendingTab) }} 将放弃当前输入；已经保存并生效的内容不会改变。</p>
        </div>
        <template #footer>
          <footer class="unsaved-dialog-footer">
            <AimaButton @click="continueEditing">
              继续编辑
            </AimaButton>
            <AimaButton
              variant="primary"
              @click="discardAndSwitch"
            >
              放弃修改并切换
            </AimaButton>
          </footer>
        </template>
      </AimaDialog>
    </main>
  </AppShell>
</template>

<style scoped>
.admin-page {
  display: grid;
  min-width: 0;
  gap: 16px;
  padding: 4px 0 8px;
}
.tabs {
  display: flex;
  min-height: 44px;
  align-items: flex-end;
  gap: 8px;
  overflow-x: auto;
  overflow-y: hidden;
}
.tabs button {
  height: 44px;
  flex: none;
  padding: 0 4px;
  border: 0;
  border-bottom: 2px solid transparent;
  color: var(--aima-text-muted);
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  font-weight: 400;
  line-height: 20px;
}
.tabs button.active {
  border-color: var(--aima-primary);
  color: var(--aima-primary);
  font-weight: 500;
}

/* 品牌目录在 Wide 下按内容收起空白高度，编辑区单独承担长表单滚动。 */
.admin-page :deep(.brand-directory-card) {
  height: auto;
  min-height: 0;
  overflow-y: visible;
}

/* AI 模型与 TikHub 保持同一个业务 Owner，只在管理员页面同步 Figma Geometry。 */
.admin-page :deep(.provider-layout) {
  grid-template-columns: 398px minmax(760px, 1fr);
  gap: 24px;
}
.admin-page :deep(.provider-list),
.admin-page :deep(.provider-form) {
  border-radius: 8px;
}
.admin-page :deep(.provider-list) {
  min-height: 620px;
}
.admin-page :deep(.provider-form input),
.admin-page :deep(.provider-form select) {
  height: 40px;
  border-radius: 8px;
  font-size: 13px;
}
.admin-page :deep(.provider-form) {
  gap: 14px;
}
.admin-page :deep(.provider-item) {
  min-height: 84px;
  border-radius: 7px;
}
.admin-page :deep(.advanced-grid label > small) {
  font-size: 11px;
}
.admin-page :deep(.runtime-rule),
.admin-page :deep(.security-note),
.admin-page :deep(.advanced-settings),
.admin-page :deep(.technical-details) {
  border-radius: 7px;
}

.unsaved-dialog-header {
  display: flex;
  min-height: 64px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 20px;
}
.unsaved-dialog-header h2,
.unsaved-dialog-header small,
.unsaved-dialog-body p {
  margin: 0;
}
.unsaved-dialog-header h2 {
  color: var(--aima-text);
  font-size: 16px;
  line-height: 22px;
}
.unsaved-dialog-header small {
  color: var(--aima-text-muted);
  font-size: 11px;
}
.unsaved-dialog-close {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  flex: none;
  border: 0;
  color: var(--aima-text-muted);
  background: transparent;
  cursor: pointer;
}
.unsaved-dialog-body {
  padding: 20px;
}
.unsaved-dialog-body p {
  color: var(--aima-text-secondary);
  font-size: 13px;
  line-height: 21px;
}
.unsaved-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 20px 20px;
}

@media (max-width: 1439px) {
  .admin-page :deep(.provider-layout) {
    grid-template-columns: 1fr;
  }
  .admin-page :deep(.provider-list),
  .admin-page :deep(.provider-form) {
    width: 100%;
    min-height: 0;
  }
}
</style>
