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

export const fetchVehicles = async (): Promise<VehicleModelListResponse> =>
  unwrapResponse(await listVehicleModels({ limit: 200 }))

export const addVehicle = async (body: VehicleModelCreateRequest) =>
  unwrapResponse(await createVehicleModel(body))

export const editVehicle = async (id: string, body: VehicleModelUpdateRequest) =>
  unwrapResponse(await updateVehicleModel(id, body))

export const removeVehicle = async (id: string): Promise<void> =>
  unwrapResponse(await deleteVehicleModel(id))

export const mergeVehicle = async (id: string, body: VehicleModelMergeRequest) =>
  unwrapResponse(await mergeVehicleModel(id, body))

export const fetchKeywordPacksForAdmin = async (): Promise<KeywordPackListResponse> =>
  unwrapResponse(await listKeywordPacks({ limit: 100 }))

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

export const fetchAuditEvents = async (): Promise<AuditEventListResponse> =>
  unwrapResponse(await listAuditEvents({ limit: 100 }))
