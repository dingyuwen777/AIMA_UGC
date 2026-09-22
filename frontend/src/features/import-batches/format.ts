import type {
  CollectionPlatform,
  CollectionRuntimeRecordType,
  CollectionRuntimeStatus,
  ImportBatchStatus,
  ImportStage,
} from '../../generated/api/client'
import { PLATFORM_LABELS } from '../../shared/domain/platform'

export const statusLabels: Record<ImportBatchStatus, string> = {
  queued: '排队中',
  running: '处理中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

export const stageLabels: Record<ImportStage, string> = {
  queued: '等待处理',
  reading: '读取数据',
  mapping: '整理字段',
  filtering: '筛选相关内容',
  deduplicating: '检查重复内容',
  ingesting: '保存内容',
  succeeded: '已完成',
  failed: '处理失败',
  cancelled: '已取消',
}

export const runtimeStatusLabels: Record<CollectionRuntimeStatus, string> = {
  queued: '排队中',
  running: '运行中',
  partial_success: '部分完成',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

export const recordTypeLabels: Record<CollectionRuntimeRecordType, string> = {
  excel_import: 'Excel 导入',
  data_import_campaign: '数据导入',
  tikhub_discovery: '平台采集',
  tikhub_batch_supplement: '辅助补采',
  canonical_replay: '历史重筛',
}

export const platformLabels: Record<CollectionPlatform, string> = PLATFORM_LABELS

const runtimeStageLabels: Record<string, string> = {
  queued: '等待处理',
  uploading: '接收文件',
  discovering: '发现数据来源',
  snapshotting: '准备导入数据',
  ready: '等待确认导入',
  running: '数据导入',
  cancelling: '正在取消',
  partial_failed: '部分失败',
  reading: '读取数据',
  mapping: '整理字段',
  filtering: '筛选相关内容',
  deduplicating: '检查重复内容',
  ingesting: '保存内容',
  content_discovery: '平台采集中',
  content_enrichment: '补充内容信息',
  replaying: '重筛并写入',
  succeeded: '已完成',
  failed: '处理失败',
  cancelled: '已取消',
}

const runtimeFailureMessages: Record<string, string> = {
  provider_secret_unavailable: '采集服务授权信息不可用，请联系管理员检查服务配置。',
  identity_unavailable: '导入内容缺少可验证的平台原生 ID，或属于不支持评论补采的微博长文章；其他内容请补充原始内容链接或原生 ID 后新建补采任务。',
  exact_resolution_unavailable: '导入内容只有分享链接等定位信息，当前渠道无法精确定位评论所属内容；请向上游补充原始内容链接或原生 ID。',
  comment_coverage_partial: 'Provider 可见评论或回复未完整补齐；请查看内容详情中的覆盖率，并从原来源新建补采任务。',
  identity_ambiguous: '来源对应多个可能的评论目标，需先确认唯一原始内容后新建补采任务。',
  identity_conflict: '解析出的平台原生 ID 已归属于另一条内容；请核对导入来源，修正关联后新建补采任务。',
  identity_resolution_unknown: '身份解析结果暂时未知，后台将按任务重试策略处理。',
  canonical_replay_artifact_invalid: '部分历史 Canonical 文件未通过完整性校验，请联系管理员检查问题记录。',
  canonical_replay_input_invalid: '部分重筛输入已失效，请联系管理员检查历史数据来源。',
}

export function runtimeStageLabel(value: string): string {
  return runtimeStageLabels[value] ?? '处理中'
}

/** 将稳定错误码转换为可操作提示；未知机器错误不直接暴露到业务主视图。 */
export function runtimeFailureMessage(value: string | null | undefined): string | null {
  if (!value) return null
  return runtimeFailureMessages[value] ?? '任务执行遇到问题；如已终止，请修复原因后新建补采任务。'
}

export function formatNumber(value: number | undefined): string {
  return new Intl.NumberFormat('zh-CN').format(value ?? 0)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export function elapsed(start: string | null | undefined, end: string | null | undefined): string {
  if (!start) return '—'
  const seconds = Math.max(0, Math.floor((new Date(end ?? Date.now()).getTime() - new Date(start).getTime()) / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  return [hours, minutes, rest].map((part) => String(part).padStart(2, '0')).join(':')
}

export function shortId(value: string): string {
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value
}
