import { config } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { routes } from '../src/app/routes'

describe('frontend bootstrap', () => {
  it('registers the home route', () => {
    expect(routes.map((route) => route.name)).toContain('home')
  })

  it('registers the formal collection runtime route', () => {
    expect(routes).toContainEqual(
      expect.objectContaining({
        path: '/collection-runtime',
        name: 'collection-runtime',
      }),
    )
  })

  it('loads Vue Test Utils', () => {
    expect(config.global).toBeDefined()
  })
})
