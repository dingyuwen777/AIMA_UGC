import type {
  CollectionCapabilitiesResponse,
  CollectionPlatform,
  KeywordPackResponse,
} from '../../generated/api/client'

export interface PlanPlatformSelection {
  platform: CollectionPlatform
  provider_config_id: string
}

export interface PlanExecutionEligibilityInput {
  keywordPackIds: readonly string[]
  vehicleModelIds: readonly string[]
  platforms: readonly PlanPlatformSelection[]
  requireRelevance: boolean
  relevanceAvailable: boolean
  packDetails: Readonly<Record<string, KeywordPackResponse>>
  capabilities: CollectionCapabilitiesResponse | null
}

/** 按当前后端 Capability、词包和全局相关性事实给出计划不可执行的首个原因。 */
export function planExecutionReason(input: PlanExecutionEligibilityInput): string | null {
  if (input.keywordPackIds.length === 0 && input.vehicleModelIds.length === 0) {
    return '请至少选择一个关键词包或车型。'
  }
  if (input.platforms.length === 0) return '请至少选择一个采集平台。'
  if (input.requireRelevance && !input.relevanceAvailable) return '全局相关性尚未配置。'

  const details: KeywordPackResponse[] = []
  for (const packId of input.keywordPackIds) {
    const pack = input.packDetails[packId]
    if (!pack) return '正在读取所选词包的实时明细。'
    if (!pack.enabled) return `关键词包“${pack.name}”当前已停用。`
    details.push(pack)
  }

  for (const selection of input.platforms) {
    const hasKeyword = input.vehicleModelIds.length > 0 || details.some((pack) =>
      pack.keywords.some(
        (keyword) =>
          keyword.enabled &&
          (keyword.platform_scope === 'all' || keyword.platform_scope === selection.platform),
      ),
    )
    if (!hasKeyword) return `采集平台 ${selection.platform} 没有可用关键词。`

    const provider = input.capabilities?.provider_configs.find(
      (item) => item.id === selection.provider_config_id,
    )
    if (!provider) return `采集平台 ${selection.platform} 的 Provider 配置当前不可用。`
    const capability = input.capabilities?.capabilities.find(
      (item) =>
        item.platform === selection.platform &&
        item.provider === provider.provider &&
        item.operations.includes('keyword_search'),
    )
    if (!capability) return `采集平台 ${selection.platform} 当前不支持关键词发现。`
  }

  return null
}
