export interface ArtifactRetentionView {
  expiresAt: string | null
  expired: boolean
}

const DAY_MS = 24 * 60 * 60 * 1000
const IMPORT_SOURCE_RETENTION_DAYS = 7
const EXPORT_RETENTION_DAYS = 7

function retentionFrom(
  baseAt: string | null | undefined,
  days: number,
  nowMs: number,
): ArtifactRetentionView {
  if (!baseAt) return { expiresAt: null, expired: false }
  const baseMs = Date.parse(baseAt)
  if (!Number.isFinite(baseMs)) return { expiresAt: null, expired: false }
  const expiresMs = baseMs + days * DAY_MS
  return {
    expiresAt: new Date(expiresMs).toISOString(),
    expired: nowMs >= expiresMs,
  }
}

export function importSourceRetention(
  finishedAt: string | null | undefined,
  nowMs = Date.now(),
): ArtifactRetentionView {
  return retentionFrom(finishedAt, IMPORT_SOURCE_RETENTION_DAYS, nowMs)
}

export function exportArtifactRetention(
  completedAt: string | null | undefined,
  nowMs = Date.now(),
): ArtifactRetentionView {
  return retentionFrom(completedAt, EXPORT_RETENTION_DAYS, nowMs)
}
