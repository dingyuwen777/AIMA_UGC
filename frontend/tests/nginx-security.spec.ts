import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const nginx = readFileSync(new URL('../nginx.conf', import.meta.url), 'utf8')

describe('frontend nginx browser security', () => {
  it('统一返回已批准的浏览器安全响应头', () => {
    const csp = [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'self'",
      "form-action 'self'",
      "script-src 'self'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https:",
      "font-src 'self' data:",
      "connect-src 'self'",
    ].join('; ')

    expect(nginx).toContain('add_header Strict-Transport-Security "max-age=31536000" always;')
    expect(nginx).toContain(`add_header Content-Security-Policy "${csp};" always;`)
    expect(nginx).toContain(
      'add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=(), usb=()" always;',
    )
    expect(nginx).toContain('add_header X-Content-Type-Options "nosniff" always;')
    expect(nginx).toContain(
      'add_header Referrer-Policy "strict-origin-when-cross-origin" always;',
    )
    expect(nginx).not.toContain('includeSubDomains')
    expect(nginx).not.toContain('preload')
  })

  it('保留现有同源代理、SPA 与 IP 加端口 HTTP 访问边界', () => {
    expect(nginx).toContain('listen 8080;')
    expect(nginx).toContain('server_name _;')
    expect(nginx).toContain('proxy_pass http://api:8090;')
    expect(nginx).toContain('try_files $uri $uri/ /index.html;')
    expect(nginx).not.toMatch(/return\s+(301|302|307|308)\s+https:/)
  })

  it('旧版跨域策略文件显式返回 404 而不是进入 SPA fallback', () => {
    expect(nginx).toMatch(/location\s*=\s*\/clientaccesspolicy\.xml\s*\{\s*return 404;/s)
    expect(nginx).toMatch(/location\s*=\s*\/crossdomain\.xml\s*\{\s*return 404;/s)
  })
})
