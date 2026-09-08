<script setup lang="ts">
import { computed, onMounted } from 'vue'

import NotificationInbox from '../../features/identity/NotificationInbox.vue'
import { useIdentityStore } from '../../features/identity/store'
import { TaskCenter } from '../../features/task-center'
import AimaIcon, { type AimaIconName } from '../../shared/ui/AimaIcon.vue'

withDefaults(defineProps<{ sectionTitle?: string }>(), { sectionTitle: '采集运行中心' })

// App Shell 只展示当前首版真实可达页面，未来能力不以无效菜单项占位。
const identity = useIdentityStore()

const navigation = computed<{ label: string; icon: AimaIconName; to: string }[]>(() => [
  { label: '首页', icon: 'home', to: '/' },
  { label: '声音广场', icon: 'voice', to: '/voice-plaza' },
  { label: '采集运行中心', icon: 'runtime', to: '/collection-runtime' },
  { label: '采集策略', icon: 'strategy', to: '/collection-strategy' },
  ...(identity.isAdministrator
    ? [{ label: '管理员配置', icon: 'settings' as const, to: '/admin/configuration' }]
    : []),
])

const principalRoleLabel = computed(() => {
  if (identity.principalError) return '身份不可用'
  if (!identity.principal) return '身份加载中'
  return identity.principal.role === 'administrator' ? '管理员' : '普通用户'
})

onMounted(() => void identity.ensurePrincipal())
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          爱
        </div>
        <div>
          <strong>爱玛用户声音</strong>
          <span>智能监测与洞察平台</span>
        </div>
      </div>

      <nav aria-label="业务导航">
        <span class="nav-group-label">业务工作台</span>
        <RouterLink
          v-for="item in navigation"
          :key="item.label"
          class="nav-item"
          :to="item.to"
        >
          <span class="nav-icon"><AimaIcon
            :name="item.icon"
            :size="16"
          /></span>
          {{ item.label }}
        </RouterLink>
      </nav>
      <footer class="sidebar-footer">
        <TaskCenter />
        <NotificationInbox />
        <div class="account-area">
          <div
            v-if="identity.principalError"
            class="principal-error"
            role="alert"
          >
            <span>身份读取失败</span>
            <button
              type="button"
              :disabled="identity.loading"
              :title="identity.principalError"
              @click="identity.retryPrincipal()"
            >
              {{ identity.loading ? '重试中…' : '重试' }}
            </button>
          </div>
          <span
            class="avatar"
            aria-label="当前用户"
          >{{ identity.principal?.display_name?.slice(0, 1) ?? '爱' }}</span>
          <div class="principal">
            <strong>{{ identity.principal?.display_name ?? (identity.principalError ? '身份不可用' : '身份加载中') }}</strong>
            <span>{{ principalRoleLabel }}</span>
          </div>
        </div>
      </footer>
    </aside>

    <section class="workspace">
      <main
        class="workspace-main"
        :aria-label="sectionTitle"
      >
        <slot />
      </main>
    </section>
  </div>
</template>

<style scoped>
.app-shell { display: flex; min-width: 0; min-height: 100vh; background: var(--aima-color-bg-page); }
.sidebar { position: fixed; inset: 0 auto 0 0; z-index: 10; display: flex; width: 180px; flex-direction: column; border-right: 1px solid var(--aima-border); background: #fff; }
.brand { display: flex; height: 76px; flex: none; align-items: center; gap: 8px; padding: 0 12px; }
.brand-mark { display: grid; width: 32px; height: 32px; flex: none; place-items: center; border-radius: 6px; color: #fff; background: var(--aima-primary); font-size: 18px; }
.brand strong, .brand span { display: block; white-space: nowrap; }
.brand strong { font-size: 14px; }
.brand span { margin-top: 4px; color: var(--aima-text-disabled); font-size: 10px; }
nav { min-height: 0; overflow-y: auto; padding: 8px 12px; }
.nav-group-label { display: block; margin-bottom: 4px; color: var(--aima-text-disabled); font-size: 10px; line-height: 16px; }
.nav-item { display: flex; min-height: 38px; align-items: center; gap: 8px; margin-bottom: 4px; padding: 8px 16px; border-radius: 8px; color: var(--aima-text); text-decoration: none; font-size: 14px; }
.nav-item.router-link-active { color: var(--aima-primary); background: var(--aima-primary-soft); font-weight: 600; }
.nav-icon { display: flex; width: 16px; flex: none; color: var(--aima-text-muted); }
.router-link-active .nav-icon { color: var(--aima-primary); }
.sidebar-footer { display: grid; flex: none; gap: 2px; margin-top: auto; padding: 12px; }
.sidebar-footer :deep(.task-center-trigger), .sidebar-footer :deep(.inbox-trigger) { display: flex; width: 100%; height: 40px; justify-content: flex-start; gap: 8px; padding: 0 8px; border: 0; border-radius: 6px; background: transparent; color: var(--aima-text-muted); font-size: 13px; }
.sidebar-footer :deep(.task-center-trigger:hover), .sidebar-footer :deep(.inbox-trigger:hover) { background: var(--aima-primary-soft); color: var(--aima-primary); }
.account-area { display: flex; min-width: 0; align-items: center; gap: 8px; padding: 8px; flex-wrap: wrap; }
.principal { display: grid; min-width: 0; flex: 1; gap: 3px; }
.principal strong { overflow: hidden; color: var(--aima-text); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.principal span { color: var(--aima-text-disabled); font-size: 10px; }
.principal-error { display: flex; width: 100%; align-items: center; justify-content: space-between; color: var(--aima-danger); font-size: 11px; }
.principal-error button { border: 0; padding: 0; background: transparent; color: var(--aima-primary); cursor: pointer; }
.avatar { display: grid; width: 30px; height: 30px; flex: none; place-items: center; border-radius: 50%; color: #fff; background: #8063ff; font-size: 14px; }
.workspace { width: calc(100% - 180px); min-width: 0; min-height: 100vh; margin-left: 180px; }
.workspace-main { width: 100%; min-width: 0; padding: 24px 24px 32px; }
@media (max-width: 767px) {
  .sidebar { width: 144px; }
  .brand { padding-inline: 8px; gap: 6px; }
  .brand strong { font-size: 12px; }
  .brand span { display: none; }
  .nav-item { padding-inline: 8px; font-size: 12px; }
  .workspace { width: calc(100% - 144px); margin-left: 144px; }
  .workspace-main { padding: 16px; }
}
</style>
