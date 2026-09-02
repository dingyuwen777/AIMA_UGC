<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { formatDateTime } from '../../shared/domain/beijingTime'
import { useIdentityStore } from './store'

const store = useIdentityStore()
const open = ref(false)
const unreadIds = computed(() => store.notifications.filter((item) => !item.is_read).map((item) => item.id))

onMounted(() => void store.refreshNotifications())

/** 切换通知面板；每次打开都从服务端重新校准未读事实。 */
async function toggle(): Promise<void> {
  open.value = !open.value
  if (open.value) await store.refreshNotifications()
}
</script>

<template>
  <div class="inbox">
    <button
      class="inbox-trigger"
      type="button"
      :aria-expanded="open"
      aria-label="站内通知"
      @click="toggle"
    >
      <span aria-hidden="true">铃</span>
      <b v-if="store.unreadCount">{{ Math.min(store.unreadCount, 99) }}</b>
    </button>
    <section
      v-if="open"
      class="inbox-panel"
      aria-label="通知列表"
    >
      <header>
        <div><strong>消息中心</strong><span>{{ store.unreadCount }} 条未读</span></div>
        <button
          type="button"
          :disabled="unreadIds.length === 0 || store.notificationLoading"
          @click="store.markRead(unreadIds)"
        >
          全部已读
        </button>
      </header>
      <div
        v-if="store.notificationError"
        class="inbox-error"
        role="alert"
      >
        <strong>通知加载失败</strong>
        <span>{{ store.notificationError }}</span>
        <button
          type="button"
          :disabled="store.notificationLoading"
          @click="store.refreshNotifications()"
        >
          {{ store.notificationLoading ? '重试中…' : '重试' }}
        </button>
      </div>
      <p v-else-if="store.notificationLoading && store.notifications.length === 0">
        正在加载…
      </p>
      <p v-else-if="store.notifications.length === 0">
        暂无通知
      </p>
      <button
        v-for="item in store.notifications"
        v-else
        :key="item.id"
        class="notification"
        :class="{ 'notification--unread': !item.is_read }"
        type="button"
        @click="store.markRead([item.id])"
      >
        <strong>{{ item.title }}</strong>
        <span>{{ item.message }}</span>
        <time>{{ formatDateTime(item.created_at) }}</time>
      </button>
    </section>
  </div>
</template>

<style scoped>
.inbox { position: relative; }
.inbox-trigger { position: relative; display: grid; width: 34px; height: 34px; place-items: center; border: 1px solid var(--aima-border); border-radius: 50%; color: var(--aima-text-secondary); background: var(--aima-surface); cursor: pointer; font-size: 11px; }
.inbox-trigger b { position: absolute; top: -5px; right: -7px; min-width: 18px; height: 18px; padding: 0 4px; border: 2px solid #fff; border-radius: 9px; color: #fff; background: var(--aima-primary); font-size: 9px; line-height: 14px; }
.inbox-panel { position: absolute; z-index: 80; top: 42px; right: 0; width: 360px; max-height: 480px; overflow: auto; border: 1px solid var(--aima-border); border-radius: 10px; background: var(--aima-surface); box-shadow: var(--aima-shadow-floating); }
.inbox-panel header { position: sticky; top: 0; display: flex; min-height: 58px; align-items: center; justify-content: space-between; padding: 0 16px; border-bottom: 1px solid var(--aima-border); background: var(--aima-surface); }
.inbox-panel header div { display: grid; gap: 3px; }
.inbox-panel header strong { color: var(--aima-text); font-size: 14px; }
.inbox-panel header span { color: var(--aima-text-muted); font-size: 10px; }
.inbox-panel header button { border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 11px; }
.inbox-panel > p { margin: 0; padding: 28px 16px; color: var(--aima-text-muted); text-align: center; }
.inbox-error { display: grid; gap: 6px; padding: 18px 16px; color: var(--aima-danger); background: #fff7f7; }
.inbox-error strong { font-size: 12px; }
.inbox-error span { color: var(--aima-text-secondary); font-size: 10px; line-height: 16px; }
.inbox-error button { justify-self: start; padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 11px; }
.notification { display: grid; width: 100%; gap: 5px; padding: 12px 16px; border: 0; border-bottom: 1px solid var(--aima-border); color: inherit; background: var(--aima-surface); cursor: pointer; text-align: left; }
.notification--unread { background: var(--aima-primary-soft); }
.notification strong { color: var(--aima-text); font-size: 12px; }
.notification span { color: var(--aima-text-secondary); font-size: 11px; line-height: 17px; }
.notification time { color: var(--aima-text-disabled); font-size: 9px; }
</style>
