<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useIdentityStore } from './features/identity/store'

const identity = useIdentityStore()
const route = useRoute()
const router = useRouter()

/** Cookie 可被其他标签页切换；恢复前台必须从服务器重新确认当前账号。 */
function revalidate(): void {
  if (document.visibilityState !== 'hidden') void identity.revalidatePrincipal()
}

watch(() => identity.scopeEpoch, () => {
  if (route.name === 'login' || route.name === 'no-access') return
  if (identity.unauthenticated) void router.replace({ name: 'login', query: { return_to: route.fullPath } })
  else if (identity.forbidden || (route.meta.requiresAdministrator && !identity.isAdministrator)) {
    void router.replace({ name: 'no-access', query: { access: 'administrator-required' } })
  }
})

onMounted(() => {
  window.addEventListener('focus', revalidate)
  document.addEventListener('visibilitychange', revalidate)
})
onBeforeUnmount(() => {
  window.removeEventListener('focus', revalidate)
  document.removeEventListener('visibilitychange', revalidate)
})
</script>

<template>
  <RouterView
    v-if="route.name === 'login' || route.name === 'no-access' || (!identity.unauthenticated && !identity.forbidden && (!route.meta.requiresAdministrator || identity.isAdministrator))"
    :key="identity.scopeEpoch"
  />
</template>
