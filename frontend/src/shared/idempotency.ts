/**
 * 为前端写请求创建 UUID v4 幂等键。
 *
 * `randomUUID()` 只在安全上下文暴露；普通 HTTP 部署回退到仍可用的
 * `getRandomValues()`，并按 Web Crypto 规范设置 UUID 版本位和变体位。
 */
export function createClientIdempotencyKey(): string {
  const cryptoApi = globalThis.crypto
  if (typeof cryptoApi?.randomUUID === 'function') return cryptoApi.randomUUID()
  if (typeof cryptoApi?.getRandomValues !== 'function') {
    throw new Error('当前浏览器不支持安全随机数生成，无法创建请求幂等键。')
  }

  const bytes = cryptoApi.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, '0'))
  return [
    hex.slice(0, 4).join(''),
    hex.slice(4, 6).join(''),
    hex.slice(6, 8).join(''),
    hex.slice(8, 10).join(''),
    hex.slice(10, 16).join(''),
  ].join('-')
}
