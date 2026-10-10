import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setTestPrincipal } from './rolePrincipal'

const api = vi.hoisted(() => ({ listVehicleBrands: vi.fn(), listVehicleModels: vi.fn() }))
vi.mock('../src/generated/api/client', () => api)
import { useVehicleCatalogStore } from '../src/shared/domain/vehicleCatalog'

const brand = { id: 'brand-1', code: 'AIMA', display_name: '爱玛', status: 'active', catalog_version: 1, version: 1 }
const response = (items: unknown[]) => ({ items, total: items.length })

describe('shared vehicle catalog', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.resetAllMocks() })

  it('账号切换清除 active/all 与名称缓存，旧请求不覆盖新账号', async () => {
    setTestPrincipal('administrator', 'A')
    let finish!: (value: unknown) => void
    api.listVehicleBrands.mockReturnValueOnce(new Promise((resolve) => { finish = resolve }))
    const store = useVehicleCatalogStore()
    const old = store.loadBrands('all')
    const rejected = expect(old).rejects.toMatchObject({ name: 'AbortError' })
    setTestPrincipal('user', 'B')
    expect(store.brands.all).toBeNull()
    expect(store.knownBrands).toEqual({})
    api.listVehicleBrands.mockResolvedValue(response([{ ...brand, display_name: 'B 名称' }]))
    await store.loadBrands('active')
    finish(response([brand]))
    await rejected
    expect(store.knownBrands['brand-1']?.display_name).toBe('B 名称')
    expect(store.brands.all).toBeNull()
  })

  it('deduplicates concurrent readers, separates scopes and preserves equal successful objects', async () => {
    let resolve!: (value: unknown) => void
    api.listVehicleBrands.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    const store = useVehicleCatalogStore()
    const first = store.loadBrands('active')
    const second = store.loadBrands('active')
    expect(api.listVehicleBrands).toHaveBeenCalledOnce()
    resolve(response([brand]))
    await Promise.all([first, second])
    const old = store.brands.active
    const name = store.knownBrands['brand-1']
    api.listVehicleBrands.mockResolvedValueOnce(response([{ ...brand }]))
    await store.loadBrands('active', true)
    expect(store.brands.active).toBe(old)
    expect(store.knownBrands['brand-1']).toBe(name)
    api.listVehicleBrands.mockResolvedValueOnce(response([brand, { ...brand, id: 'inactive', status: 'inactive' }]))
    await store.loadBrands('all')
    expect(store.brands.active).toHaveLength(1)
    expect(store.brands.all).toHaveLength(2)
    expect(api.listVehicleBrands).toHaveBeenLastCalledWith({ status: undefined, offset: 0, limit: 200 })
  })

  it('retains the successful catalog and readable names while delayed refresh fails', async () => {
    api.listVehicleModels.mockResolvedValueOnce(response([{ id: 'vehicle-1', display_name: '爱玛 Q7', brand_id: 'brand-1' }]))
    const store = useVehicleCatalogStore()
    await store.loadVehicles()
    const old = store.vehicles.active
    let reject!: (value: unknown) => void
    api.listVehicleModels.mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail }))
    const pending = store.loadVehicles('active', true)
    expect(store.vehicleLoading.active).toBe(true)
    expect(store.vehicles.active).toBe(old)
    expect(store.knownVehicles['vehicle-1']?.display_name).toBe('爱玛 Q7')
    reject(new Error('暂时不可用'))
    await expect(pending).rejects.toThrow('暂时不可用')
    expect(store.vehicles.active).toBe(old)
    expect(store.vehicleErrors.active).toBeTruthy()
  })

  it('does not let an older scope response replace a newer known identity', async () => {
    let resolve!: (value: unknown) => void
    api.listVehicleBrands.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    const store = useVehicleCatalogStore()
    const old = store.loadBrands('all')
    api.listVehicleBrands.mockResolvedValueOnce(response([{ ...brand, display_name: '新名称', catalog_version: 2, version: 2 }]))
    await store.loadBrands('active')
    resolve(response([brand]))
    await old
    expect(store.knownBrands['brand-1']?.display_name).toBe('新名称')
    api.listVehicleBrands.mockResolvedValueOnce(response([]))
    await store.loadBrands('active', true)
    expect(store.activeBrands).toEqual([])
    expect(store.knownBrands['brand-1']?.display_name).toBe('新名称')
  })
})
