import { describe, expect, it } from 'vitest'

import {
  exportArtifactRetention,
  importSourceRetention,
} from '../src/shared/artifactRetention'

describe('artifact retention display', () => {
  it('derives the Excel import source deadline from terminal time', () => {
    const retention = importSourceRetention(
      '2026-08-24T00:00:00.000Z',
      Date.parse('2026-08-30T23:59:59.000Z'),
    )

    expect(retention.expiresAt).toBe('2026-08-31T00:00:00.000Z')
    expect(retention.expired).toBe(false)
  })

  it('keeps an unfinished import without a fabricated deadline', () => {
    expect(importSourceRetention(null, Date.parse('2026-08-30T00:00:00.000Z'))).toEqual({
      expiresAt: null,
      expired: false,
    })
  })

  it('marks an Excel export expired seven days after completion', () => {
    const retention = exportArtifactRetention(
      '2026-08-24T00:00:00.000Z',
      Date.parse('2026-08-31T00:00:00.000Z'),
    )

    expect(retention.expiresAt).toBe('2026-08-31T00:00:00.000Z')
    expect(retention.expired).toBe(true)
  })
})
