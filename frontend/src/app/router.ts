import { createRouter, createWebHistory } from 'vue-router'

import { useIdentityStore } from '../features/identity/store'
import { routes } from './routes'

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const identity = useIdentityStore()
  const principal = await identity.ensurePrincipal()
  if (to.meta.requiresAdministrator && principal?.role !== 'administrator') {
    return { name: 'home', query: { access: 'administrator-required' } }
  }
  return true
})
