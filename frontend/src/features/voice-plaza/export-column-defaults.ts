import {
  getMyExportColumnDefault,
  updateMyExportColumnDefault,
  type ExportColumnDefaultResponse,
  type ExportColumnDefaultUpdateRequest,
} from '../../generated/api/client'
import { unwrapResponse } from '../../shared/api/http'

/** 当前 Session 决定配置归属，客户端不传目标账号。 */
export async function fetchMyExportColumnDefault(): Promise<ExportColumnDefaultResponse> {
  return unwrapResponse(await getMyExportColumnDefault())
}

/** 显式保存才修改长期默认；临时导出不经过此入口。 */
export async function saveMyExportColumnDefault(
  request: ExportColumnDefaultUpdateRequest,
): Promise<ExportColumnDefaultResponse> {
  return unwrapResponse(await updateMyExportColumnDefault(request))
}
