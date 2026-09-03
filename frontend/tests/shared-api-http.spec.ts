import { describe, expect, it } from 'vitest'

import { AimaApiError, apiErrorMessage, unwrapResponse } from '../src/shared/api/http'

describe('shared HTTP Contract errors', () => {
  it('shows safe Contract fields and codes with request_id for administration diagnostics', () => {
    const response = {
      type: 'about:blank',
      title: '请求参数错误',
      status: 422,
      detail: '请求未通过 Contract 校验。',
      request_id: 'request-admin-contract',
      errors: [
        { field: 'query.limit', code: 'less_than_equal', message: '输入应小于等于上限' },
      ],
    }

    const error = (() => {
      try {
        unwrapResponse(response)
        return null
      } catch (reason) {
        return reason
      }
    })()

    expect(error).toBeInstanceOf(AimaApiError)
    expect(apiErrorMessage(error)).toBe(
      '请求未通过 Contract 校验。（query.limit: less_than_equal）（request_id: request-admin-contract）',
    )
    expect((error as AimaApiError).errors).toHaveLength(1)
  })
})
