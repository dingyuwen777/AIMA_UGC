import { createRouter, createWebHistory } from 'vue-router'

import { identityGuard } from './identity-guard'
import { routes } from './routes'

export { identityGuard } from './identity-guard'
export type { IdentityGuardResult } from './identity-guard'

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => identityGuard(to))
