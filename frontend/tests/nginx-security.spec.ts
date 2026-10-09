import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const nginx = readFileSync(new URL('../nginx.conf', import.meta.url), 'utf8')
const streamLocation = nginx.match(/location ~ (\^\/api\/v1\/contents\/\S+) \{([\s\S]*?)\n        \}/)

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
      "media-src 'self'",
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

  it('视频精确路由透传 Range 与 Cookie，不缓冲缓存或记录签名会话', () => {
    const stream = streamLocation?.[2]
    expect(stream).toBeDefined()
    expect(stream).toContain('access_log off;')
    expect(stream).toContain('error_log /dev/null;')
    expect(stream).toContain('proxy_buffering off;')
    expect(stream).toContain('proxy_request_buffering off;')
    expect(stream).toContain('proxy_max_temp_file_size 0;')
    expect(stream).toContain('proxy_http_version 1.1;')
    expect(stream).toContain('proxy_read_timeout 120s;')
    expect(stream).toContain('add_header Cache-Control "private, no-store" always;')
    expect(stream).toContain('add_header Referrer-Policy "no-referrer" always;')
    expect(stream).not.toMatch(/proxy_set_header\s+(Range|Cookie)\s+""/)
    expect(nginx).not.toMatch(/media-src[^;]*https:/)
  })

  it('所有后端合法路径别名和尾斜杠重定向均进入视频保护路由，其他 API 保留日志', () => {
    expect(streamLocation).not.toBeNull()
    const protectedPath = new RegExp(streamLocation![1]!)
    const uuid = '10000000-0000-4000-8000-000000000001'
    for (const contentId of [uuid, uuid.replaceAll('-', ''), `{${uuid}}`, `urn:uuid:${uuid}`]) {
      for (const position of ['0', '+0', '-0', '00', '0.0', ' 0 ']) {
        for (const suffix of ['', '/']) {
          expect(protectedPath.test(`/api/v1/contents/${contentId}/media/${position}/playback/stream${suffix}`)).toBe(true)
        }
      }
    }
    for (const path of [
      `/api/v1/contents/${uuid}/media/0/playback/prepare`,
      `/api/v1/contents/${uuid}/media/0`,
      '/api/v1/jobs/job-1',
      `/api/v1/contents/${uuid}/media/0/playback/streaming`,
    ]) expect(protectedPath.test(path)).toBe(false)
    expect(nginx.match(/access_log off;/g)).toHaveLength(1)
    expect(nginx.match(/error_log \/dev\/null;/g)).toHaveLength(1)
    expect(nginx).toContain('access_log /dev/stdout;')
    expect(nginx).toContain('error_log /dev/stderr warn;')
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
