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

  it('registers the formal voice plaza route', () => {
    expect(routes).toContainEqual(
      expect.objectContaining({
        path: '/voice-plaza',
        name: 'voice-plaza',
      }),
    )
  })

  it('registers collection strategy as a first-level business route', () => {
    expect(routes).toContainEqual(
      expect.objectContaining({
        path: '/collection-strategy',
        name: 'collection-strategy',
      }),
    )
  })

  it('loads Vue Test Utils', () => {
    expect(config.global).toBeDefined()
  })
})
