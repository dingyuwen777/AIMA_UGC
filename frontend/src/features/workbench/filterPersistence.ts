import { PlatformName } from '../../generated/api/client'
import type { WorkbenchFilters } from './store'
import { ownsPrincipalFilters } from '../../shared/api/principalScope'

const storageKey = 'aima.workbench.applied-filters'
const listFields = ['platforms', 'brandIds', 'vehicleModelIds', 'voiceTypes', 'sentiments', 'primaryLabels', 'secondaryLabels'] as const

/** 校验自然日的实际日历值，损坏存储不能变成非法 API 日期。 */
function validDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const parsed = new Date(`${value}T00:00:00Z`)
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

/** 只恢复已应用条件；返回值还须用当前目录及 Taxonomy 归一化。 */
export function readWorkbenchFilters(): WorkbenchFilters | null {
  if (!ownsPrincipalFilters()) return null
  try {
    const raw = sessionStorage.getItem(storageKey)
    if (!raw) return null
    const value: unknown = JSON.parse(raw)
    if (!value || typeof value !== 'object') throw new Error('无效筛选快照')
    const saved = value as Record<string, unknown>
    if (saved.schema_version !== 1 || !validDate(saved.dateFrom) || !validDate(saved.dateTo)
      || !listFields.every((key) => Array.isArray(saved[key]) && saved[key].every((item: unknown) => typeof item === 'string'))) {
      throw new Error('无效筛选快照')
    }
    const result = Object.fromEntries(listFields.map((key) => [key, [...new Set(saved[key] as string[])]])) as Pick<WorkbenchFilters, typeof listFields[number]>
    result.platforms = result.platforms.filter((item) => Object.values(PlatformName).includes(item))
    return { ...result, dateFrom: saved.dateFrom, dateTo: saved.dateTo }
  } catch {
    try { sessionStorage.removeItem(storageKey) } catch { /* 浏览器禁用存储时仍允许使用工作台。 */ }
    return null
  }
}

/** 白名单序列化，禁止把聚合响应、分页游标或布局草稿写入浏览器存储。 */
export function saveWorkbenchFilters(filters: WorkbenchFilters): void {
  if (!ownsPrincipalFilters()) return
  try {
    sessionStorage.setItem(storageKey, JSON.stringify({
      schema_version: 1,
      dateFrom: filters.dateFrom,
      dateTo: filters.dateTo,
      ...Object.fromEntries(listFields.map((key) => [key, [...filters[key]]])),
    }))
  } catch { /* 存储不可用时保留本页筛选与正常请求。 */ }
}
