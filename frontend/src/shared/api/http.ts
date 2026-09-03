import type { HttpErrorItem, HttpErrorResponse } from '../../generated/api/client'

function contractErrorSummary(errors: readonly HttpErrorItem[] | undefined): string | null {
  if (!errors?.length) return null
  return errors
    .slice(0, 3)
    .map((item) => `${item.field || 'request'}: ${item.code}`)
    .join('；')
}

export function httpErrorDetail(response: HttpErrorResponse): string {
  const summary = contractErrorSummary(response.errors)
  return summary ? `${response.detail}（${summary}）` : response.detail
}

export class AimaApiError extends Error {
  readonly status: number
  readonly requestId: string
  readonly errors: readonly HttpErrorItem[]

  constructor(response: HttpErrorResponse) {
    super(httpErrorDetail(response))
    this.name = 'AimaApiError'
    this.status = response.status
    this.requestId = response.request_id
    this.errors = response.errors ?? []
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
