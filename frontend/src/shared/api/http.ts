import type { HttpErrorResponse } from '../../generated/api/client'

export class AimaApiError extends Error {
  readonly status: number
  readonly requestId: string

  constructor(response: HttpErrorResponse) {
    super(response.detail)
    this.name = 'AimaApiError'
    this.status = response.status
    this.requestId = response.request_id
  }
}

export function isHttpErrorResponse(value: unknown): value is HttpErrorResponse {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  return typeof candidate.status === 'number'
    && typeof candidate.detail === 'string'
    && typeof candidate.request_id === 'string'
}

export function unwrapResponse<T>(value: T): T {
  if (isHttpErrorResponse(value)) throw new AimaApiError(value)
  return value
}

export function apiErrorMessage(error: unknown): string {
  if (error instanceof AimaApiError) {
    return `${error.message}（request_id: ${error.requestId}）`
  }
  if (error instanceof Error && error.message) return error.message
  return '请求失败，请稍后重试。'
}
