import {
  capturePrincipalScope, isPrincipalScopeCurrent, waitForPrincipalValidation,
} from './principalScope'

/** 正式 generated Client 的唯一 fetch mutator；身份变化后拒绝迟到响应。 */
export async function aimaRequest<T>(url: string, options?: RequestInit): Promise<T> {
  const identityRequest = /\/api\/v1\/(?:principal|auth\/logout)(?:\?|$)/.test(url)
  const epoch = capturePrincipalScope()
  if (!identityRequest) await waitForPrincipalValidation()
  if (!identityRequest && !isPrincipalScopeCurrent(epoch)) throw new DOMException('账号已切换，请重新加载。', 'AbortError')
  const response = await fetch(url, options)
  const body = [204, 205, 304].includes(response.status) ? null
    : response.headers.get('content-type')?.includes('json') ? await response.json() : await response.blob()
  // 发送期间另一个标签页可能切换 Cookie；身份复核结束前不提交响应。
  if (!identityRequest) await waitForPrincipalValidation()
  if (!identityRequest && !isPrincipalScopeCurrent(epoch)) throw new DOMException('账号已切换，请重新加载。', 'AbortError')
  return body as T
}
