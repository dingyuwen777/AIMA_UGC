import {
  getContentAnalysisTaxonomy,
  getWorkbenchLayout,
  getWorkbenchMind,
  getWorkbenchStream,
  getWorkbenchTrend,
  updateWorkbenchLayout,
  type BrandResponse,
  type ContentAnalysisTaxonomyResponse,
  type GetWorkbenchMindParams,
  type GetWorkbenchStreamParams,
  type GetWorkbenchTrendParams,
  type VehicleModelResponse,
  type WorkbenchLayoutResponse,
  type WorkbenchLayoutUpdateRequest,
  type WorkbenchMindResponse,
  type WorkbenchStreamResponse,
  type WorkbenchTrendResponse,
} from '../../generated/api/client'
import { unwrapResponse } from '../../shared/api/http'
import { useVehicleCatalogStore } from '../../shared/domain/vehicleCatalog'

/** 读取当前 active Analysis Scheme 的安全 Taxonomy 投影。 */
export async function fetchWorkbenchTaxonomy(): Promise<ContentAnalysisTaxonomyResponse> {
  return unwrapResponse(await getContentAnalysisTaxonomy())
}

/** 读取声音流模块；参数只来自 generated Workbench Contract。 */
export async function fetchWorkbenchStream(
  params: GetWorkbenchStreamParams,
): Promise<WorkbenchStreamResponse> {
  return unwrapResponse(await getWorkbenchStream(params))
}

/** 读取 UGC 声量与情感趋势模块。 */
export async function fetchWorkbenchTrend(
  params: GetWorkbenchTrendParams,
): Promise<WorkbenchTrendResponse> {
  return unwrapResponse(await getWorkbenchTrend(params))
}

/** 读取 active Taxonomy 一级标签驱动的品牌用户心智模块。 */
export async function fetchWorkbenchMind(
  params: GetWorkbenchMindParams,
): Promise<WorkbenchMindResponse> {
  return unwrapResponse(await getWorkbenchMind(params))
}

/** 读取当前 Principal 的有效工作台布局；无持久配置时后端返回默认 revision=0。 */
export async function fetchWorkbenchLayout(): Promise<WorkbenchLayoutResponse> {
  return unwrapResponse(await getWorkbenchLayout())
}

/** 以 revision CAS 保存完整布局草稿，冲突由统一 HTTP Error Contract 显式返回。 */
export async function saveWorkbenchLayout(
  request: WorkbenchLayoutUpdateRequest,
): Promise<WorkbenchLayoutResponse> {
  return unwrapResponse(await updateWorkbenchLayout(request))
}

/** 分页读取全部 active 品牌，避免 200 条 API 页上限静默截断选择器。 */
export async function fetchActiveBrands(): Promise<BrandResponse[]> {
  return useVehicleCatalogStore().loadBrands('active', true)
}

/** 分页读取全部 active 车型，筛选器不把首个 Offset 页误当完整目录。 */
export async function fetchActiveVehicleModels(): Promise<VehicleModelResponse[]> {
  return useVehicleCatalogStore().loadVehicles('active', true)
}
