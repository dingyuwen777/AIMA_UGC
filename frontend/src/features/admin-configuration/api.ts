import {
  createAnalysisSchemeDraft,
  createVehicleModel,
  deleteVehicleModel,
  listAnalysisSchemes,
  listAuditEvents,
  listKeywordPacks,
  listVehicleModels,
  mergeVehicleModel,
  publishAnalysisScheme,
  replaceKeywordPackVehicleModels,
  rollbackAnalysisScheme,
  updateAnalysisSchemeDraft,
  updateVehicleModel,
  type AnalysisSchemeCreateDraftRequest,
  type AnalysisSchemeListResponse,
  type AnalysisSchemeResponse,
  type AnalysisSchemeUpdateDraftRequest,
  type AuditEventListResponse,
  type KeywordPackListResponse,
  type VehicleModelCreateRequest,
  type VehicleModelListResponse,
  type VehicleModelMergeRequest,
  type VehicleModelUpdateRequest,
} from '../../generated/api/client'
import { unwrapResponse } from '../../shared/api/http'

/** 分页读取全部车型，避免管理配置在车型超过单页上限时截断。 */
export async function fetchVehicles(): Promise<VehicleModelListResponse> {
  const first = unwrapResponse(await listVehicleModels({ offset: 0, limit: 200 }))
  const items = [...first.items]
  let offset = items.length
  while (offset < first.total) {
    const page = unwrapResponse(await listVehicleModels({ offset, limit: 200 }))
    if (page.items.length === 0) break
    items.push(...page.items)
    offset += page.items.length
  }
  return { ...first, items, offset: 0 }
}

export const addVehicle = async (body: VehicleModelCreateRequest) =>
  unwrapResponse(await createVehicleModel(body))

export const editVehicle = async (id: string, body: VehicleModelUpdateRequest) =>
  unwrapResponse(await updateVehicleModel(id, body))

export const removeVehicle = async (id: string): Promise<void> =>
  unwrapResponse(await deleteVehicleModel(id))

export const mergeVehicle = async (id: string, body: VehicleModelMergeRequest) =>
  unwrapResponse(await mergeVehicleModel(id, body))

/** 分页读取全部词包，保证管理配置使用完整后端目录。 */
export async function fetchKeywordPacksForAdmin(): Promise<KeywordPackListResponse> {
  const first = unwrapResponse(await listKeywordPacks({ offset: 0, limit: 100 }))
  const items = [...first.items]
  let offset = items.length
  while (offset < first.total) {
    const page = unwrapResponse(await listKeywordPacks({ offset, limit: 100 }))
    if (page.items.length === 0) break
    items.push(...page.items)
    offset += page.items.length
  }
  return { ...first, items, offset: 0 }
}

export const saveKeywordPackVehicles = async (packId: string, vehicleModelIds: string[]) =>
  unwrapResponse(await replaceKeywordPackVehicleModels(packId, { vehicle_model_ids: vehicleModelIds }))

export const fetchSchemes = async (): Promise<AnalysisSchemeListResponse> =>
  unwrapResponse(await listAnalysisSchemes())

export const addSchemeDraft = async (body: AnalysisSchemeCreateDraftRequest): Promise<AnalysisSchemeResponse> =>
  unwrapResponse(await createAnalysisSchemeDraft(body))

export const editSchemeDraft = async (id: string, body: AnalysisSchemeUpdateDraftRequest): Promise<AnalysisSchemeResponse> =>
  unwrapResponse(await updateAnalysisSchemeDraft(id, body))

export const activateScheme = async (id: string, expectedVersion: number): Promise<AnalysisSchemeResponse> =>
  unwrapResponse(await publishAnalysisScheme(id, { expected_version: expectedVersion }))

export const restoreScheme = async (id: string, expectedVersion: number): Promise<AnalysisSchemeResponse> =>
  unwrapResponse(await rollbackAnalysisScheme(id, { expected_version: expectedVersion }))

export const fetchAuditEvents = async (
  offset = 0,
  limit = 100,
): Promise<AuditEventListResponse> =>
  unwrapResponse(await listAuditEvents({ offset, limit }))
