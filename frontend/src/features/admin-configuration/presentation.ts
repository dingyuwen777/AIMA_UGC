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
  analysis_scheme_created: '新建 AI 分析方案',
  analysis_scheme_draft_created: '新建 AI 分析方案草稿',
  analysis_scheme_draft_updated: '更新 AI 分析方案草稿',
  analysis_scheme_published: '发布 AI 分析方案',
  analysis_scheme_rolled_back: '回滚 AI 分析方案',
  keyword_pack_vehicle_links_updated: '更新词包车型关联',
  provider_config_created: '新建模型服务配置',
  provider_config_test_failed: '模型服务测试失败',
  provider_config_test_succeeded: '模型服务测试通过',
  provider_config_updated: '更新模型服务配置',
  taxonomy_runtime_created: '新建标签规则',
  taxonomy_runtime_published: '发布标签规则',
  taxonomy_runtime_updated: '更新标签规则',
  vehicle_model_created: '新增车型',
  vehicle_model_deleted: '删除车型',
  vehicle_model_merged: '合并车型',
  vehicle_model_updated: '更新车型',
}

const AUDIT_OBJECT_LABELS: Record<string, string> = {
  analysis_scheme: 'AI 分析方案',
  collection_provider_config: '采集服务',
  keyword_pack: '词包',
  keyword_pack_vehicle_links: '词包车型关联',
  llm_provider_config: 'AI 模型服务',
  provider_config: '模型服务',
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

/**
 * 从 safe_detail 中只提炼明确、非敏感的数量信息。
 * 未识别结构时退回保守说明，绝不根据 JSON 字段猜测业务结论。
 */
export function auditSummaryText(event: AuditEventResponse): string {
  const detail = event.safe_detail ?? {}
  const changedCount = changedFieldCount(detail)

  if (event.event_type === 'provider_config_updated') {
    return changedCount == null
      ? '已记录本次模型服务配置操作'
      : `已更新 ${changedCount} 项模型服务设置`
  }
  if (event.event_type === 'provider_config_created') return '已创建新的模型服务配置'
  if (event.event_type === 'provider_config_test_succeeded') return '连接与配置校验通过'
  if (event.event_type === 'provider_config_test_failed') return '连接或配置校验未通过'

  const objectLabel = auditObjectLabel(event.object_type, event.object_id)
  return `已记录本次${objectLabel}操作`
}
