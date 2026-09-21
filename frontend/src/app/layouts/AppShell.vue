<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { resolveAvatarUrl } from '../../features/identity/avatar'
import NotificationInbox from '../../features/identity/NotificationInbox.vue'
import { LOGIN_PATH, useIdentityStore } from '../../features/identity/store'
import { TaskCenter } from '../../features/task-center'
import AimaIcon, { type AimaIconName } from '../../shared/ui/AimaIcon.vue'

withDefaults(defineProps<{ sectionTitle?: string }>(), { sectionTitle: '采集运行中心' })

// App Shell 只展示当前首版真实可达页面，未来能力不以无效菜单项占位。
const identity = useIdentityStore()

const navigation = computed<{ label: string; icon: AimaIconName; to: string }[]>(() => [
  { label: '工作台', icon: 'home', to: '/' },
  { label: '声音广场', icon: 'voice', to: '/voice-plaza' },
  { label: '采集运行中心', icon: 'runtime', to: '/collection-runtime' },
  { label: '采集策略', icon: 'strategy', to: '/collection-strategy' },
  ...(identity.isAdministrator
    ? [{ label: '管理员配置', icon: 'settings' as const, to: '/admin/configuration' }]
    : []),
])

/**
 * 身份区当前处于哪种状态。
 *
 * 直接复用 store 里**已有**的 `outcome`（身份层已经把失败分成了 401 / 403 / 其他传输错误），
 * 展示层只把这三类翻译成用户看得懂的话 —— 不新增前端状态，也不在这里重新判断状态码。
 */
const identityState = computed<'ready' | 'unauthenticated' | 'forbidden' | 'error' | 'loading'>(() => {
  if (identity.principal) return 'ready'
  if (identity.outcome === 'unauthenticated') return 'unauthenticated'
  if (identity.outcome === 'forbidden') return 'forbidden'
  if (identity.outcome === 'error') return 'error'
  return 'loading'
})

/** 角色文字：只在身份正常时使用（`administrator` → 管理员，其余 → 普通用户）。 */
const principalRoleLabel = computed(() =>
  identity.principal?.role === 'administrator' ? '管理员' : '普通用户',
)

/** 异常态文字：未登录 / 无权限 / 服务异常各自说清楚，不再笼统显示「身份不可用」。 */
const stateLabel = computed(() => {
  switch (identityState.value) {
    case 'unauthenticated':
      return '未登录'
    case 'forbidden':
      return '无权限'
    case 'error':
      return '服务异常'
    default:
      return '身份加载中'
  }
})

/** 图片加载失败的本地标记；只由真实 `error` 事件置位，不做 URL 猜测。 */
const avatarFailed = ref(false)

const avatarUrl = computed(() => resolveAvatarUrl(identity.principal?.avatar_url, avatarFailed.value))

/** 回退头像文字：姓名首字；连姓名都没有时用品牌字，避免头像位置出现空白。 */
const avatarFallbackText = computed(() => identity.principal?.display_name?.trim().slice(0, 1) || '爱')

/** 权限来源提示（悬浮可见）：告诉用户权限是谁给的、要去哪里改。 */
const permissionHint = computed(() => {
  if (identity.principal?.source === 'feishu') {
    return '权限来自飞书用户组；如需调整，请联系管理员在飞书后台修改用户组成员'
  }
  if (identity.principal) {
    return '当前为本地开发身份，权限不来自飞书用户组'
  }
  if (identityState.value === 'unauthenticated') {
    return '当前没有有效会话，请先通过飞书登录'
  }
  if (identityState.value === 'forbidden') {
    return '已登录，但不在允许使用本系统的飞书用户组内；请联系管理员把你加入用户组'
  }
  if (identityState.value === 'error') {
    return identity.principalError ?? '身份服务暂时不可用'
  }
  return '正在读取当前身份…'
})

/**
 * 部门行文字：只有拿到**非空**部门名时才返回字符串，否则返回 `null`（模板据此整行不渲染）。
 *
 * 为什么要在这里把 undefined / null / 空串 / 纯空格统一收口：后端该字段是可选的，
 * 登录时向飞书取部门失败就不写值；若直接插值，界面会出现「部门：null」或「部门：」这类
 * **看着像数据、其实是假信息**的内容 —— 那比整行不显示更糟，用户会以为系统丢了数据。
 * 顺带也覆盖了异步场景：身份还没加载完时 `principal` 为 null，这里自然返回 null，不显示部门行。
 */
const departmentLabel = computed(() => {
  const name = identity.principal?.department_name?.trim()
  return name ? `部门：${name}` : null
})

/** 退出登录：服务端撤销会话后整页回到首页，确保内存里的身份状态被彻底丢掉。 */
async function handleLogout(): Promise<void> {
  await identity.logout()
  window.location.assign('/')
}
onMounted(() => void identity.ensurePrincipal())
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-top">
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
      </div>

      <footer class="sidebar-footer">
        <TaskCenter />
        <div class="account-area">
          <!-- 权限来源用 title 悬浮提示，不占用本就紧张的侧栏横向空间。 -->
          <div
            class="account-identity"
            :title="permissionHint"
          >
            <span
              class="avatar"
              aria-label="当前用户"
            >
              <img
                v-if="avatarUrl"
                class="avatar-image"
                :src="avatarUrl"
                alt=""
                @error="avatarFailed = true"
              >
              <template v-else>{{ avatarFallbackText }}</template>
            </span>
            <div
              v-if="identityState === 'ready'"
              class="principal"
            >
              <strong class="principal-name">{{ identity.principal?.display_name }}</strong>
              <span
                class="role-badge"
                :class="identity.principal?.role === 'administrator'
                  ? 'role-badge--administrator'
                  : 'role-badge--user'"
              >{{ principalRoleLabel }}</span>
              <!--
                部门是**追加**在姓名、角色之后的第三行，不改动前两行 —— 这样不会重新分配
                已在 180px 侧栏上调平的横向宽度，姓名可用宽度仍为约 107px，短姓名继续完整可见。
                悬浮 `title` 兜底被省略号截断的超长部门名。
              -->
              <span
                v-if="departmentLabel"
                class="principal-department"
                :title="departmentLabel"
              >{{ departmentLabel }}</span>
            </div>
            <div
              v-else
              class="principal principal--notice"
              :role="identityState === 'error' ? 'alert' : undefined"
            >
              <strong class="principal-name">{{ stateLabel }}</strong>
              <RouterLink
                v-if="identityState === 'unauthenticated'"
                class="principal-action"
                :to="LOGIN_PATH"
              >
                去登录
              </RouterLink>
              <span
                v-else-if="identityState === 'forbidden'"
                class="principal-hint"
              >联系管理员</span>
              <button
                v-else-if="identityState === 'error'"
                type="button"
                class="principal-action"
                :disabled="identity.loading"
                @click="identity.retryPrincipal()"
              >
                {{ identity.loading ? '重试中…' : '重试' }}
              </button>
            </div>
          </div>

          <div class="account-actions">
            <button
              type="button"
              class="logout"
              title="退出登录"
              @click="handleLogout"
            >
              退出
            </button>
            <NotificationInbox compact />
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
.sidebar { position: fixed; inset: 0 auto 0 0; z-index: 10; display: flex; width: 180px; flex-direction: column; padding: 20px 12px; border-right: 1px solid var(--aima-border); background: #fff; }
.sidebar-top { display: flex; min-height: 0; flex: 1; flex-direction: column; gap: 24px; }
.brand { display: flex; min-height: 32px; flex: none; align-items: center; gap: 8px; }
.brand-mark { display: grid; width: 32px; height: 32px; flex: none; place-items: center; border-radius: 6px; color: #fff; background: var(--aima-primary); font-size: 16px; font-weight: 500; line-height: 24px; }
.brand strong, .brand span { display: block; white-space: nowrap; }
.brand strong { color: var(--aima-text); font-size: 14px; font-weight: 500; line-height: 22px; }
.brand span { margin-top: 2px; color: var(--aima-text-disabled); font-size: 11px; line-height: 16px; }
nav { min-width: 0; min-height: 0; overflow-x: hidden; overflow-y: auto; }
.nav-group-label { display: block; margin-bottom: 4px; color: var(--aima-text-disabled); font-size: 11px; line-height: 16px; }
.nav-item { display: flex; width: 100%; min-height: 38px; align-items: center; gap: 8px; padding: 8px 16px; border-radius: 8px; color: var(--aima-text); text-decoration: none; font-size: 14px; line-height: 22px; }
.nav-item + .nav-item { margin-top: 4px; }
.nav-item.router-link-active { color: var(--aima-primary); background: var(--aima-primary-soft); font-weight: 500; }
.nav-icon { display: flex; width: 16px; flex: none; color: var(--aima-text-muted); }
.router-link-active .nav-icon { color: var(--aima-primary); }
.sidebar-footer { display: grid; flex: none; gap: 8px; margin-top: auto; }
.sidebar-footer :deep(.task-center-trigger) { display: flex; width: 100%; height: 35px; justify-content: flex-start; gap: 6px; padding: 8px; border: 0; border-radius: 6px; background: transparent; color: var(--aima-text-muted); font-size: 13px; line-height: 22px; }
.sidebar-footer :deep(.task-center-trigger:hover) { background: var(--aima-primary-soft); color: var(--aima-primary); }
/*
 * 账户区改成两行：第一行是"头像 + 姓名 + 角色"，第二行才是操作（退出 / 消息）。
 * 原因：180px 侧栏减去内外边距后内容宽约 139px，旧版把 32px 头像 + 32px 退出 + 28px 铃铛
 * 再加 24px 间距（共 116px）全塞在同一行，留给姓名只剩约 20px —— 于是**短名字也会被截成「N…」**，
 * 角色的「普通用户」也会被挤到换行。操作下沉一行后，姓名可用宽度约 107px，短名字完整可见。
 */
.account-area { display: grid; min-width: 0; gap: 6px; padding: 8px 4px 0; border-top: 1px solid var(--aima-border); }
.account-identity { display: flex; min-width: 0; align-items: center; gap: 8px; }
.principal { display: grid; min-width: 0; flex: 1; gap: 2px; }
.principal-name { overflow: hidden; color: var(--aima-text); font-size: 13px; font-weight: 500; line-height: 18px; text-overflow: ellipsis; white-space: nowrap; }
/* 角色徽标：管理员橙色实心、普通用户灰色浅底，做到一眼可辨。 */
.role-badge { justify-self: start; max-width: 100%; overflow: hidden; padding: 0 6px; border-radius: var(--aima-radius-full); text-overflow: ellipsis; white-space: nowrap; font-size: 10px; line-height: 16px; }
.role-badge--administrator { color: var(--aima-color-text-inverse); background: var(--aima-color-info-badge); font-weight: 500; }
.role-badge--user { color: var(--aima-text-muted); background: var(--aima-color-bg-hover); }
.principal-hint { overflow: hidden; color: var(--aima-text-muted); font-size: 10px; line-height: 16px; text-overflow: ellipsis; white-space: nowrap; }
/*
 * 部门行：姓名/角色之后**追加的第三行**，属次要信息，故沿用弱化色（--aima-text-muted）与 10px。
 * 这里是**纵向**追加、不重分横向宽度 —— 姓名所在的那一列宽度完全没变，所以不会把姓名挤成「N…」。
 * 部门名往往最长（如 Project_Aima_CN01P000637，约 24 字符 > 可用宽度 107px），故单行省略号收尾，
 * 完整值由模板上的 title 悬浮展示：宁可次要信息被截且可查，也不让它撑破 180px 侧栏。
 */
.principal-department { overflow: hidden; color: var(--aima-text-muted); font-size: 10px; line-height: 16px; text-overflow: ellipsis; white-space: nowrap; }
.principal-action { justify-self: start; border: 0; padding: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 11px; line-height: 16px; text-decoration: none; }
.principal-action:hover { text-decoration: underline; }
.principal-action:disabled { color: var(--aima-text-disabled); cursor: default; text-decoration: none; }
.account-actions { display: flex; min-width: 0; align-items: center; justify-content: flex-end; gap: 4px; }
.logout { flex: none; border: 0; padding: 4px; background: transparent; color: var(--aima-text-muted); cursor: pointer; font-size: 12px; }
.logout:hover { color: var(--aima-primary); }
.avatar { display: grid; width: 32px; height: 32px; flex: none; place-items: center; overflow: hidden; border-radius: 50%; color: #fff; background: #7b61ff; font-size: 13px; font-weight: 500; line-height: 22px; }
.avatar-image { width: 100%; height: 100%; object-fit: cover; }
.workspace { width: calc(100% - 180px); min-width: 0; min-height: 100vh; margin-left: 180px; }
.workspace-main { width: 100%; min-width: 0; padding: 24px 24px 32px; }
@media (max-width: 767px) {
  .sidebar { width: 144px; padding-inline: 8px; }
  .brand { gap: 6px; }
  .brand strong { font-size: 12px; }
  .brand span { display: none; }
  .nav-item { padding-inline: 8px; font-size: 12px; }
  .workspace { width: calc(100% - 144px); margin-left: 144px; }
  .workspace-main { padding: 16px; }
  /*
   * 窄屏优先保头像，隐藏"姓名 + 角色徽标"这组常态信息；
   * 但异常态的提示与操作（去登录 / 联系管理员 / 重试）必须留下 —— 否则窄屏用户
   * 遇到服务异常时既看不到原因也点不到重试。
   */
  .principal { display: none; }
  .principal--notice { display: grid; }
}
</style>
