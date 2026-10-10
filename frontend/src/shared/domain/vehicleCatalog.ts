import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import {
  listVehicleBrands, listVehicleModels,
  type BrandResponse, type VehicleModelResponse,
} from '../../generated/api/client'
import { apiErrorMessage, unwrapResponse } from '../api/http'
import { useIdentityStore } from '../../features/identity/store'

type CatalogScope = 'active' | 'all'

/** 目录只由此 Owner 分页读取；成功值在刷新期间保留，active/all 不互相污染。 */
export const useVehicleCatalogStore = defineStore('vehicle-catalog', () => {
  const identity = useIdentityStore()
  const brands = ref<Record<CatalogScope, BrandResponse[] | null>>({ active: null, all: null })
  const vehicles = ref<Record<CatalogScope, VehicleModelResponse[] | null>>({ active: null, all: null })
  const brandLoading = ref({ active: false, all: false })
  const vehicleLoading = ref({ active: false, all: false })
  const brandErrors = ref<Record<CatalogScope, string | null>>({ active: null, all: null })
  const vehicleErrors = ref<Record<CatalogScope, string | null>>({ active: null, all: null })
  const knownBrands = ref<Record<string, BrandResponse>>({})
  const knownVehicles = ref<Record<string, VehicleModelResponse>>({})
  const brandRequests: Partial<Record<CatalogScope, Promise<BrandResponse[]>>> = {}
  const vehicleRequests: Partial<Record<CatalogScope, Promise<VehicleModelResponse[]>>> = {}
  const brandFetchedAt = { active: 0, all: 0 }
  const vehicleFetchedAt = { active: 0, all: 0 }
  const freshFor = 5 * 60 * 1000

  async function loadBrands(scope: CatalogScope = 'active', force = false): Promise<BrandResponse[]> {
    const epoch = identity.scopeEpoch
    if (brandRequests[scope]) return brandRequests[scope]
    if (!force && brands.value[scope] !== null && Date.now() - brandFetchedAt[scope] < freshFor) return brands.value[scope]!
    brandLoading.value[scope] = true
    brandErrors.value[scope] = null
    const request = (async () => {
      try {
        const items: BrandResponse[] = []
        let offset = 0
        while (true) {
          const page = unwrapResponse(await listVehicleBrands({
            status: scope === 'active' ? 'active' : undefined, offset, limit: 200,
          }))
          if (epoch !== identity.scopeEpoch) throw new DOMException('账号已切换', 'AbortError')
          if (!Array.isArray(page.items)) throw new Error('品牌目录响应无效，请稍后重试。')
          items.push(...page.items)
          offset += page.items.length
          if (!page.items.length || offset >= page.total) break
        }
        if (JSON.stringify(brands.value[scope]) !== JSON.stringify(items)) brands.value[scope] = items
        for (const item of items) {
          const known = knownBrands.value[item.id]
          if ((!known || item.catalog_version > known.catalog_version || (item.catalog_version === known.catalog_version && item.version >= known.version))
            && JSON.stringify(known) !== JSON.stringify(item)) knownBrands.value[item.id] = item
        }
        brandFetchedAt[scope] = Date.now()
        return brands.value[scope]!
      } catch (error) {
        if (epoch === identity.scopeEpoch) brandErrors.value[scope] = apiErrorMessage(error)
        throw error
      } finally {
        if (epoch === identity.scopeEpoch) {
          brandLoading.value[scope] = false
          delete brandRequests[scope]
        }
      }
    })()
    brandRequests[scope] = request
    return request
  }

  async function loadVehicles(scope: CatalogScope = 'active', force = false): Promise<VehicleModelResponse[]> {
    const epoch = identity.scopeEpoch
    if (vehicleRequests[scope]) return vehicleRequests[scope]
    if (!force && vehicles.value[scope] !== null && Date.now() - vehicleFetchedAt[scope] < freshFor) return vehicles.value[scope]!
    vehicleLoading.value[scope] = true
    vehicleErrors.value[scope] = null
    const request = (async () => {
      try {
        const items: VehicleModelResponse[] = []
        let offset = 0
        while (true) {
          const page = unwrapResponse(await listVehicleModels({
            status: scope === 'active' ? 'active' : undefined, offset, limit: 200,
          }))
          if (epoch !== identity.scopeEpoch) throw new DOMException('账号已切换', 'AbortError')
          if (!Array.isArray(page.items)) throw new Error('车型目录响应无效，请稍后重试。')
          items.push(...page.items)
          offset += page.items.length
          if (!page.items.length || offset >= page.total) break
        }
        if (JSON.stringify(vehicles.value[scope]) !== JSON.stringify(items)) vehicles.value[scope] = items
        for (const item of items) {
          const known = knownVehicles.value[item.id]
          if ((!known || item.catalog_version > known.catalog_version || (item.catalog_version === known.catalog_version && item.version >= known.version))
            && JSON.stringify(known) !== JSON.stringify(item)) knownVehicles.value[item.id] = item
        }
        vehicleFetchedAt[scope] = Date.now()
        return vehicles.value[scope]!
      } catch (error) {
        if (epoch === identity.scopeEpoch) vehicleErrors.value[scope] = apiErrorMessage(error)
        throw error
      } finally {
        if (epoch === identity.scopeEpoch) {
          vehicleLoading.value[scope] = false
          delete vehicleRequests[scope]
        }
      }
    })()
    vehicleRequests[scope] = request
    return request
  }

  const activeBrands = computed(() => brands.value.active ?? [])
  /** active/all、已知目录与在途请求同属当前 Principal，角色切换也不能沿用。 */
  watch(() => identity.scopeEpoch, () => {
    brands.value = { active: null, all: null }
    vehicles.value = { active: null, all: null }
    knownBrands.value = {}
    knownVehicles.value = {}
    for (const scope of ['active', 'all'] as const) {
      delete brandRequests[scope]
      delete vehicleRequests[scope]
      brandFetchedAt[scope] = 0
      vehicleFetchedAt[scope] = 0
      brandLoading.value[scope] = false
      vehicleLoading.value[scope] = false
      brandErrors.value[scope] = null
      vehicleErrors.value[scope] = null
    }
  }, { flush: 'sync' })
  const activeVehicles = computed(() => vehicles.value.active ?? [])
  return { brands, vehicles, brandLoading, vehicleLoading, brandErrors, vehicleErrors,
    knownBrands, knownVehicles, activeBrands, activeVehicles, loadBrands, loadVehicles }
})
