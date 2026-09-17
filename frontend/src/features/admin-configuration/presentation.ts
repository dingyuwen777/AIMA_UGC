import type { AuditEventResponse } from '../../generated/api/client'

const STATUS_LABELS: Record<string, string> = {
  active: '生效中',
  cancelled: '已取消',
  cancelling: '取消中',
  deprecated: '已停用',
  disabled: '已停用',
  draft: '草稿',
  enabled: '已启用',
  failed: '失败',
  merged: '已合并',
  partial_failed: '部分失败',
  pending: '等待中',
  published: '已发布',
  queued: '排队中',
  retired: '历史版本',
  running: '运行中',
  succeeded: '已完成',
}

const AUDIT_ACTION_LABELS: Record<string, string> = {
  analysis_scheme_archived: '归档 AI 分析规则',
  analysis_scheme_copied: '复制 AI 分析规则',
  analysis_scheme_created: '新建 AI 分析规则',
  analysis_scheme_deleted: '删除 AI 分析规则',
  analysis_scheme_draft_created: '新建 AI 分析规则草稿',
  analysis_scheme_draft_updated: '更新 AI 分析规则草稿',
  analysis_scheme_published: '发布 AI 分析规则',
  analysis_scheme_restored: '恢复 AI 分析规则',
  analysis_scheme_rolled_back: '回滚 AI 分析规则',
  collection_plan_archived: '归档采集计划',
  collection_plan_copied: '复制采集计划',
  collection_plan_deleted: '删除采集计划',
  collection_plan_restored: '恢复采集计划',
  collection_plan_updated: '更新采集计划',
  data_import_campaign_revoked: '撤销数据导入',
  keyword_pack_archived: '归档词包',
  keyword_pack_copied: '复制词包',
  keyword_pack_deleted: '删除词包',
  keyword_pack_keyword_removed: '移除词包关键词',
  keyword_pack_keyword_updated: '修改词包关键词',
  keyword_pack_restored: '恢复词包',
  keyword_pack_updated: '更新词包',
  provider_config_archived: '归档服务配置',
  provider_config_created: '新建服务配置',
  provider_config_deleted: '删除服务配置',
  provider_config_restored: '恢复服务配置',
  provider_config_test_failed: '服务连接测试失败',
  provider_config_test_succeeded: '服务连接测试通过',
  provider_config_updated: '更新服务配置',
  provider_connection_tested: '测试服务连接',
  taxonomy_runtime_created: '新建标签规则',
  taxonomy_runtime_published: '发布标签规则',
  taxonomy_runtime_updated: '更新标签规则',
  vehicle_model_created: '新增车型',
  vehicle_model_deleted: '删除车型',
  vehicle_model_merged: '合并车型',
  vehicle_model_updated: '更新车型',
}

const AUDIT_OBJECT_LABELS: Record<string, string> = {
  analysis_scheme: 'AI 分析规则',
  collection_plan: '采集计划',
  collection_provider_config: '采集服务',
  data_import_campaign: '数据导入',
  keyword_pack: '词包',
  llm_provider_config: 'AI 模型服务',
  provider_config: '服务配置',
  runtime_config: '运行配置',
  taxonomy_runtime: '标签规则',
  vehicle_model: '车型',
}

/** 将后端状态码翻译为业务可读文案；未知状态不猜测其含义。 */
export function formatRuntimeStatus(status?: string | null): string {
  const normalized = status?.trim().toLowerCase()
  if (!normalized) return '当前状态'
  return STATUS_LABELS[normalized] ?? '当前状态'
}

/** 审计默认视图只展示业务动作；原始 event_type 留在技术详情中。 */
export function auditActionLabel(eventType?: string | null): string {
  const normalized = eventType?.trim().toLowerCase()
  if (!normalized) return '配置操作'
  return AUDIT_ACTION_LABELS[normalized] ?? '配置操作'
}

/** 审计默认视图不暴露 object_id；原始对象身份留在技术详情中。 */
export function auditObjectLabel(objectType?: string | null, _objectId?: string | null): string {
  const normalized = objectType?.trim().toLowerCase()
  if (!normalized) return '配置对象'
  return AUDIT_OBJECT_LABELS[normalized] ?? '配置对象'
}

/** actor_ref 是业务审计身份；仅对系统/空值做可读化，不改写真实人工身份。 */
export function auditActorLabel(actorRef?: string | null): string {
  const normalized = actorRef?.trim()
  if (!normalized) return '未记录'
  if (normalized.toLowerCase() === 'system') return '系统'
  return normalized
}

function changedFieldCount(detail: Record<string, unknown>): number | null {
  const fields = detail.changed_fields
  return Array.isArray(fields) ? fields.length : null
}

function safeCount(detail: Record<string, unknown>, key: string): number | null {
  const value = detail[key]
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
}

/**
 * 从 safe_detail 中只提炼后端明确写入、非敏感的业务事实。
 * 未识别结构时退回保守说明，绝不根据原始 JSON 或技术标识猜测业务结论。
 */
export function auditSummaryText(event: AuditEventResponse): string {
  const detail = event.safe_detail ?? {}
  const changedCount = changedFieldCount(detail)

  if (event.event_type === 'provider_config_updated') {
    return changedCount == null
      ? '已记录本次服务配置操作'
      : `已更新 ${changedCount} 项服务设置`
  }
  if (event.event_type === 'provider_config_created') return '已创建新的服务配置'
  if (event.event_type === 'provider_config_test_succeeded') return '连接与配置校验通过'
  if (event.event_type === 'provider_config_test_failed') return '连接或配置校验未通过'
  if (event.event_type === 'provider_connection_tested') {
    const ok = detail.ok
    const latency = safeCount(detail, 'latency_ms')
    const result = ok === true ? '连接测试通过' : ok === false ? '连接测试未通过' : '已完成连接测试'
    return latency == null ? result : `${result}，耗时 ${latency} 毫秒`
  }

  if (event.event_type === 'data_import_campaign_revoked') {
    const affected = safeCount(detail, 'affected_content_count')
    const hidden = safeCount(detail, 'hidden_content_count')
    const retained = safeCount(detail, 'retained_shared_content_count')
    if (affected !== null && hidden !== null && retained !== null) {
      return `撤销影响 ${affected} 条内容，其中隐藏 ${hidden} 条，共享来源保留 ${retained} 条`
    }
    return '已撤销本次数据导入的来源贡献'
  }

  if (event.event_type === 'keyword_pack_copied') return '已创建词包副本，副本默认停用'
  if (event.event_type === 'collection_plan_copied') return '已创建采集计划副本，副本默认停用'
  if (event.event_type === 'analysis_scheme_copied') return '已创建 AI 分析规则副本草稿'
  if (event.event_type === 'keyword_pack_restored') return '已恢复词包，恢复后保持停用'
  if (event.event_type === 'collection_plan_restored') return '已恢复采集计划，恢复后保持停用'
  if (event.event_type === 'provider_config_restored') return '已恢复服务配置，恢复后保持停用'
  if (event.event_type === 'analysis_scheme_restored') return '已恢复 AI 分析规则，恢复后不会自动发布'

  const objectLabel = auditObjectLabel(event.object_type, event.object_id)
  return `已记录本次${objectLabel}操作`
}
