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

  it('maps known lifecycle audit events and keeps unknown events conservative', () => {
    expect(auditActionLabel('provider_config_updated')).toBe('更新服务配置')
    expect(auditActionLabel('provider_connection_tested')).toBe('测试服务连接')
    expect(auditActionLabel('keyword_pack_archived')).toBe('归档词包')
    expect(auditActionLabel('collection_plan_restored')).toBe('恢复采集计划')
    expect(auditActionLabel('analysis_scheme_copied')).toBe('复制 AI 分析规则')
    expect(auditActionLabel('data_import_campaign_revoked')).toBe('撤销数据导入')
    expect(auditActionLabel('taxonomy_runtime_created')).toBe('新建标签规则')
    expect(auditActionLabel('analysis_scheme_published')).toBe('发布 AI 分析规则')
    expect(auditActionLabel('unknown_event')).toBe('配置操作')
  })

  it('keeps technical object identifiers out of the default business label', () => {
    expect(auditObjectLabel('provider_config', 'provider-openai')).toBe('服务配置')
    expect(auditObjectLabel('collection_plan', 'plan-opaque')).toBe('采集计划')
    expect(auditObjectLabel('data_import_campaign', 'campaign-opaque')).toBe('数据导入')
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
    expect(auditSummaryText(event)).toBe('已更新 2 项服务设置')
    expect(auditSummaryText({ ...event, safe_detail: {} })).toBe('已记录本次服务配置操作')
  })

  it('summarizes connection tests and data import revocation from explicit safe audit facts', () => {
    const base = {
      id: 'audit-2',
      object_id: 'opaque-id',
      actor_ref: 'administrator',
      request_id: 'req-456',
      created_at: '2026-09-07T08:00:00Z',
    }

    const connectionEvent = {
      ...base,
      event_type: 'provider_connection_tested',
      object_type: 'provider_config',
      safe_detail: { ok: true, latency_ms: 126 },
    } satisfies AuditEventResponse
    expect(auditSummaryText(connectionEvent)).toBe('连接测试通过，耗时 126 毫秒')

    const revocationEvent = {
      ...base,
      event_type: 'data_import_campaign_revoked',
      object_type: 'data_import_campaign',
      safe_detail: {
        affected_content_count: 25,
        hidden_content_count: 18,
        retained_shared_content_count: 7,
        recomputed_content_count: 25,
      },
    } satisfies AuditEventResponse
    expect(auditSummaryText(revocationEvent)).toBe('撤销影响 25 条内容，其中隐藏 18 条，共享来源保留 7 条')
  })

  it('explains copy and restore semantics without exposing source identifiers', () => {
    const base = {
      id: 'audit-3',
      object_id: 'opaque-id',
      actor_ref: 'administrator',
      request_id: 'req-789',
      created_at: '2026-09-07T08:00:00Z',
    }

    expect(auditSummaryText({
      ...base,
      event_type: 'keyword_pack_copied',
      object_type: 'keyword_pack',
      safe_detail: { source_keyword_pack_id: 'secret-ish-id', enabled: false },
    })).toBe('已创建词包副本，副本默认停用')
    expect(auditSummaryText({
      ...base,
      event_type: 'provider_config_restored',
      object_type: 'provider_config',
      safe_detail: { revision: 3 },
    })).toBe('已恢复服务配置，恢复后保持停用')
    expect(auditSummaryText({
      ...base,
      event_type: 'analysis_scheme_restored',
      object_type: 'analysis_scheme',
      safe_detail: {},
    })).toBe('已恢复 AI 分析规则，恢复后不会自动发布')
  })
})
