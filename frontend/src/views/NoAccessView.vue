<script setup lang="ts">
import { useIdentityStore } from '../features/identity/store'

const identity = useIdentityStore()

/**
 * 无权限页。
 *
 * ⚠️ **刻意不提供"重新登录"入口**：后端已经明确回答 403（已登录但角色不足，
 * 或不属于任何用户组）。再走一次授权仍会得到同样的结果，那会变成
 * 「403 → 登录 → 403」的死循环（任务书 H6）。这里只给出**退出登录**，
 * 让用户能换成别的账号，而不是被困在原地。
 */
function handleLogout(): void {
  void identity.logout().then(() => window.location.assign('/'))
}
</script>

<template>
  <div class="no-access-page">
    <div class="no-access-card">
      <h1>无访问权限</h1>
      <p class="detail">
        当前账号（{{ identity.principal?.display_name ?? '未知用户' }}）不在允许使用本系统的用户组内。
        请联系管理员将你加入相应的飞书用户组。
      </p>
      <button
        type="button"
        class="logout-action"
        @click="handleLogout"
      >
        退出登录
      </button>
    </div>
  </div>
</template>

<style scoped>
.no-access-page { display: grid; min-height: 100vh; place-items: center; background: var(--aima-color-bg-page); }
.no-access-card { display: grid; width: 380px; gap: 12px; padding: 32px; border: 1px solid var(--aima-border); border-radius: 12px; background: #fff; text-align: center; }
.no-access-card h1 { margin: 0; color: var(--aima-text); font-size: 18px; line-height: 26px; }
.detail { margin: 0; color: var(--aima-text-muted); font-size: 13px; line-height: 20px; }
.logout-action { margin-top: 8px; padding: 10px 16px; border: 1px solid var(--aima-border); border-radius: 8px; background: #fff; color: var(--aima-text); cursor: pointer; font-size: 14px; line-height: 22px; }
</style>
