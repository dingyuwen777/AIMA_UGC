"""一次性修复 Stage 2 后端 Brand 强约束与现有车型管理 UI 的兼容；由 workflow 验证后删除。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, got {count}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Admin API: page only consumes active Brands; Brand CRUD UI remains Stage 6 productization scope.
path = "frontend/src/features/admin-configuration/api.ts"
replace_once(
    path,
    "  listArchivedProviderConfigs,\n  listAuditEvents,\n",
    "  listArchivedProviderConfigs,\n  listAuditEvents,\n  listVehicleBrands,\n",
)
replace_once(
    path,
    "  type AnalysisSchemeUpdateDraftRequest,\n  type AuditEventListResponse,\n",
    "  type AnalysisSchemeUpdateDraftRequest,\n  type AuditEventListResponse,\n  type BrandListResponse,\n",
)
replace_once(
    path,
    "export const addVehicle = async (body: VehicleModelCreateRequest) =>\n",
    "export async function fetchVehicleBrandsForAdmin(): Promise<BrandListResponse> {\n"
    "  const first = unwrapResponse(await listVehicleBrands({ status: 'active', offset: 0, limit: 200 }))\n"
    "  const items = [...first.items]\n"
    "  let offset = items.length\n"
    "  while (offset < first.total) {\n"
    "    const page = unwrapResponse(await listVehicleBrands({ status: 'active', offset, limit: 200 }))\n"
    "    if (page.items.length === 0) break\n"
    "    items.push(...page.items)\n"
    "    offset += page.items.length\n"
    "  }\n"
    "  return { ...first, items, offset: 0 }\n"
    "}\n\n"
    "export const addVehicle = async (body: VehicleModelCreateRequest) =>\n",
)

# Admin page: bind active Vehicle explicitly to an active Brand instead of relying on a backend default.
path = "frontend/src/features/admin-configuration/pages/AdminConfigurationPage.vue"
replace_once(
    path,
    "  AuditEventResponse,\n  KeywordPackSummaryResponse,\n",
    "  AuditEventResponse,\n  BrandResponse,\n  KeywordPackSummaryResponse,\n",
)
replace_once(
    path,
    "  fetchAuditEvents,\n  fetchKeywordPacksForAdmin,\n",
    "  fetchAuditEvents,\n  fetchKeywordPacksForAdmin,\n  fetchVehicleBrandsForAdmin,\n",
)
replace_once(
    path,
    "const vehicles = ref<VehicleModelResponse[]>([])\nconst packs = ref<KeywordPackSummaryResponse[]>([])\n",
    "const vehicles = ref<VehicleModelResponse[]>([])\nconst brands = ref<BrandResponse[]>([])\nconst packs = ref<KeywordPackSummaryResponse[]>([])\n",
)
replace_once(
    path,
    "const vehicleLoading = ref(false)\nconst packLoading = ref(false)\n",
    "const vehicleLoading = ref(false)\nconst brandLoading = ref(false)\nconst packLoading = ref(false)\n",
)
replace_once(
    path,
    "const vehicleError = ref<string | null>(null)\nconst packError = ref<string | null>(null)\n",
    "const vehicleError = ref<string | null>(null)\nconst brandError = ref<string | null>(null)\nconst packError = ref<string | null>(null)\n",
)
replace_once(
    path,
    "const vehicleDraft = reactive({ id: '', code: '', displayName: '', seriesName: '', categoryName: '', aliases: '', status: 'active' as 'active' | 'deprecated' })\n",
    "const vehicleDraft = reactive({ id: '', code: '', displayName: '', brandId: '', seriesName: '', categoryName: '', aliases: '', status: 'active' as 'active' | 'deprecated' })\n",
)
replace_once(
    path,
    "const vehicleFormValid = computed(() => Boolean(\n  vehicleDraft.code.trim() && vehicleDraft.displayName.trim(),\n))\n",
    "const vehicleFormValid = computed(() => Boolean(\n  vehicleDraft.code.trim()\n    && vehicleDraft.displayName.trim()\n    && (vehicleDraft.status !== 'active' || vehicleDraft.brandId),\n))\n",
)
replace_once(
    path,
    "  if (tab.value === 'vehicles') return vehicleLoading.value\n  if (tab.value === 'links') return vehicleLoading.value || packLoading.value\n",
    "  if (tab.value === 'vehicles') return vehicleLoading.value || brandLoading.value\n  if (tab.value === 'links') return vehicleLoading.value || packLoading.value\n",
)
replace_once(
    path,
    "  if (tab.value === 'vehicles') return vehicleError.value\n",
    "  if (tab.value === 'vehicles') return vehicleError.value ?? brandError.value\n",
)
replace_once(
    path,
    "async function loadPacks(): Promise<void> {\n",
    "async function loadBrands(): Promise<void> {\n"
    "  brandLoading.value = true\n"
    "  brandError.value = null\n"
    "  try {\n"
    "    brands.value = (await fetchVehicleBrandsForAdmin()).items\n"
    "  } catch (reason) {\n"
    "    brandError.value = apiErrorMessage(reason)\n"
    "  } finally {\n"
    "    brandLoading.value = false\n"
    "  }\n"
    "}\n\n"
    "async function loadPacks(): Promise<void> {\n",
)
replace_once(
    path,
    "  await Promise.all([loadVehicles(), loadPacks(), loadSchemes(), loadAudit()])\n",
    "  await Promise.all([loadVehicles(), loadBrands(), loadPacks(), loadSchemes(), loadAudit()])\n",
)
replace_once(
    path,
    "  if (tab.value === 'vehicles') return loadVehicles()\n",
    "  if (tab.value === 'vehicles') {\n"
    "    await Promise.all([loadVehicles(), loadBrands()])\n"
    "    return\n"
    "  }\n",
)
replace_once(
    path,
    "  Object.assign(vehicleDraft, { id: '', code: '', displayName: '', seriesName: '', categoryName: '', aliases: '', status: 'active' })\n",
    "  Object.assign(vehicleDraft, { id: '', code: '', displayName: '', brandId: '', seriesName: '', categoryName: '', aliases: '', status: 'active' })\n",
)
replace_once(
    path,
    "    displayName: item.display_name,\n    seriesName: item.series_name ?? '',\n",
    "    displayName: item.display_name,\n    brandId: item.brand_id ?? '',\n    seriesName: item.series_name ?? '',\n",
)
replace_once(
    path,
    "  if (!vehicleDraft.code.trim() || !vehicleDraft.displayName.trim()) return\n",
    "  if (!vehicleFormValid.value) return\n",
)
replace_once(
    path,
    "      await editVehicle(vehicleDraft.id, {\n        display_name: vehicleDraft.displayName,\n        series_name: vehicleDraft.seriesName.trim() || null,\n",
    "      await editVehicle(vehicleDraft.id, {\n        display_name: vehicleDraft.displayName,\n        brand_id: vehicleDraft.brandId || null,\n        series_name: vehicleDraft.seriesName.trim() || null,\n",
)
replace_once(
    path,
    "      await addVehicle({\n        code: vehicleDraft.code,\n        display_name: vehicleDraft.displayName,\n        series_name: vehicleDraft.seriesName.trim() || null,\n",
    "      await addVehicle({\n        code: vehicleDraft.code,\n        display_name: vehicleDraft.displayName,\n        brand_id: vehicleDraft.brandId,\n        series_name: vehicleDraft.seriesName.trim() || null,\n",
)
replace_once(
    path,
    "          <label>\n            系列（可选）\n",
    "          <label>\n"
    "            品牌\n"
    "            <select v-model=\"vehicleDraft.brandId\">\n"
    "              <option value=\"\">\n"
    "                请选择品牌\n"
    "              </option>\n"
    "              <option\n"
    "                v-for=\"brand in brands\"\n"
    "                :key=\"brand.id\"\n"
    "                :value=\"brand.id\"\n"
    "              >\n"
    "                {{ brand.display_name }}\n"
    "              </option>\n"
    "            </select>\n"
    "            <small v-if=\"brands.length === 0\">当前没有可用品牌；请先通过品牌目录管理 API 创建 active 品牌。</small>\n"
    "            <small v-else>active 车型必须显式绑定一个当前可用品牌。</small>\n"
    "          </label>\n"
    "          <label>\n"
    "            系列（可选）\n",
)

# Full-stack: seed a real active Brand, then bind it through the UI. No hidden/default binding.
path = "frontend/e2e-fullstack/admin-product-capabilities.spec.ts"
replace_once(
    path,
    "async function createKeywordPack(request: APIRequestContext, suffix: string): Promise<{ id: string; name: string }> {\n",
    "async function createVehicleBrand(request: APIRequestContext, suffix: string): Promise<{ id: string; name: string }> {\n"
    "  const name = `全栈品牌 ${suffix}`\n"
    "  const created = await request.post('/api/v1/vehicle-brands', {\n"
    "    data: {\n"
    "      code: `FS-BRAND-${suffix}`,\n"
    "      display_name: name,\n"
    "      role: 'owned',\n"
    "      aliases: [`全栈品牌${suffix}`],\n"
    "    },\n"
    "  })\n"
    "  expect(created.status()).toBe(201)\n"
    "  const brand = await created.json() as { id: string; display_name: string }\n"
    "  expect(brand.display_name).toBe(name)\n"
    "  return { id: brand.id, name }\n"
    "}\n\n"
    "async function createKeywordPack(request: APIRequestContext, suffix: string): Promise<{ id: string; name: string }> {\n",
)
replace_once(
    path,
    "  const alias = '爱玛 U2 车型证据全栈导入'\n  const pack = await createKeywordPack(request, suffix)\n\n",
    "  const alias = '爱玛 U2 车型证据全栈导入'\n  const brand = await createVehicleBrand(request, suffix)\n  const pack = await createKeywordPack(request, suffix)\n\n",
)
replace_once(
    path,
    "  await page.getByLabel('显示名称').fill(displayName)\n  await page.getByLabel('系列（可选）').fill('全栈系列')\n",
    "  await page.getByLabel('显示名称').fill(displayName)\n  await page.getByLabel('品牌', { exact: true }).selectOption(brand.id)\n  await page.getByLabel('系列（可选）').fill('全栈系列')\n",
)
replace_once(
    path,
    "  const vehicles = await vehiclesResponse.json() as { items: { id: string; code: string; series_name: string; category_name: string }[] }\n",
    "  const vehicles = await vehiclesResponse.json() as { items: { id: string; code: string; brand_id: string | null; series_name: string; category_name: string }[] }\n",
)
replace_once(
    path,
    "  expect(vehicle, '浏览器创建的车型必须能从正式目录 API 重读').toBeTruthy()\n  expect(vehicle?.series_name).toBe('全栈系列')\n",
    "  expect(vehicle, '浏览器创建的车型必须能从正式目录 API 重读').toBeTruthy()\n  expect(vehicle?.brand_id).toBe(brand.id)\n  expect(vehicle?.series_name).toBe('全栈系列')\n",
)

print("Stage 2 admin Brand selector compatibility patch applied")
