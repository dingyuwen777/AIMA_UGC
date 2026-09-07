import { describe, expect, it } from 'vitest'

import type { AuditEventResponse } from '../src/generated/api/client'
import {
  auditActionLabel,
  auditActorLabel,
  auditObjectLabel,
  auditSummaryText,
  formatRuntimeStatus,
} from '../src/features/admin-configuration/presentation'

describe('admin configuration presentation helpers', () => {
  it('maps runtime states to Chinese business language', () => {
    expect(formatRuntimeStatus('draft')).toBe('草稿')
    expect(formatRuntimeStatus('active')).toBe('生效中')
    expect(formatRuntimeStatus('enabled')).toBe('已启用')
    expect(formatRuntimeStatus('cancelled')).toBe('已取消')
    expect(formatRuntimeStatus('custom_state')).toBe('当前状态')
  })

  it('maps known audit events and keeps unknown events conservative', () => {
    expect(auditActionLabel('provider_config_updated')).toBe('更新模型服务配置')
    expect(auditActionLabel('provider_config_test_succeeded')).toBe('模型服务测试通过')
    expect(auditActionLabel('taxonomy_runtime_created')).toBe('新建标签规则')
    expect(auditActionLabel('analysis_scheme_published')).toBe('发布 AI 分析规则')
    expect(auditActionLabel('unknown_event')).toBe('配置操作')
  })

  it('keeps technical object identifiers out of the default business label', () => {
    expect(auditObjectLabel('provider_config', 'provider-openai')).toBe('模型服务')
    expect(auditObjectLabel('taxonomy_runtime', 'taxonomy-v2')).toBe('标签规则')
    expect(auditObjectLabel('analysis_scheme', 'analysis-v2')).toBe('AI 分析规则')
    expect(auditObjectLabel('unknown_type', 'opaque-id')).toBe('配置对象')
  })

  it('uses safe detail only for concise, non-sensitive business summaries', () => {
    const event = {
      id: 'audit-1',
      event_type: 'provider_config_updated',
      object_type: 'provider_config',
      object_id: 'provider-openai',
      actor_ref: 'admin@example.com',
      safe_detail: {
        changed_fields: ['api_key', 'temperature'],
        config: { provider: 'openai', api_key: '***', temperature: 0.2 },
      },
      request_id: 'req-123',
      created_at: '2026-09-07T08:00:00Z',
    } satisfies AuditEventResponse

    expect(auditActorLabel(event.actor_ref)).toBe('admin@example.com')
    expect(auditActorLabel('system')).toBe('系统')
    expect(auditActorLabel(null)).toBe('未记录')
    expect(auditSummaryText(event)).toBe('已更新 2 项模型服务设置')
    expect(auditSummaryText({ ...event, safe_detail: {} })).toBe('已记录本次模型服务配置操作')
  })
})
