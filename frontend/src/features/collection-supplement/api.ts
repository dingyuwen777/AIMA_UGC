import {
  createCollectionRun, getCollectionCapabilities, getCollectionRun, previewCollectionSupplement,
  type CollectionRunCreateRequest, type CollectionSupplementPreviewRequest,
} from '../../generated/api/client'
import { unwrapResponse } from '../../shared/api/http'

/** 两个补采入口共用生成 Client，执行和查询继续属于 Collection。 */
export async function previewSupplement(request: CollectionSupplementPreviewRequest) {
  return unwrapResponse(await previewCollectionSupplement(request))
}
/** 创建已经确认数量和指纹的统一补采 Run。 */
export async function createSupplement(request: CollectionRunCreateRequest) {
  return unwrapResponse(await createCollectionRun(request))
}
/** 读取正式 Provider 配置与操作能力，供两个入口校验选项。 */
export async function fetchSupplementCapabilities() {
  return unwrapResponse(await getCollectionCapabilities())
}
/** 使用持久 Run 状态跟进本页创建的补采任务。 */
export async function fetchSupplementRun(runId: string) {
  return unwrapResponse(await getCollectionRun(runId))
}
