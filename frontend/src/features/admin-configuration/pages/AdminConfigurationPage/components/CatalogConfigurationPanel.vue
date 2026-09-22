<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import type { BrandResponse, VehicleModelResponse } from '../../../../../generated/api/client'
import { apiErrorMessage } from '../../../../../shared/api/http'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaDialog from '../../../../../shared/ui/AimaDialog.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import {
  addBrand,
  addBrandAlias,
  addVehicle,
  editBrand,
  editVehicle,
  fetchVehicleBrandsForAdmin,
  fetchVehicles,
  mergeVehicle,
  removeBrand,
  removeBrandAlias,
  removeVehicle,
} from '../../../api'
import { formatRuntimeStatus } from '../../../presentation'

const saving = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)
const vehicles = ref<VehicleModelResponse[]>([])
const brands = ref<BrandResponse[]>([])
const selectedBrandId = ref('')

const brandCreateOpen = ref(false)
const vehicleEditorOpen = ref(false)
const brandDeleteTarget = ref<BrandResponse | null>(null)
const vehicleDeleteTarget = ref<VehicleModelResponse | null>(null)
const resourceConflict = ref<string | null>(null)

const brandDraft = reactive({
  id: '',
  displayName: '',
  role: 'owned' as 'owned' | 'competitor' | 'other',
  aliases: '',
  status: 'active' as 'active' | 'deprecated',
})
const vehicleDraft = reactive({
  id: '',
  displayName: '',
  brandId: '',
  seriesName: '',
  aliases: '',
  status: 'active' as 'active' | 'deprecated',
})
const mergeTargetId = ref('')

const emit = defineEmits<{
  'dirty-change': [dirty: boolean]
}>()

const selectedBrand = computed(() => brands.value.find((item) => item.id === selectedBrandId.value) ?? null)
const selectedBrandVehicles = computed(() => vehicles.value.filter((item) => item.brand_id === selectedBrandId.value))
const brandFormValid = computed(() => Boolean(brandDraft.displayName.trim()))
const vehicleFormValid = computed(() => Boolean(
  vehicleDraft.displayName.trim()
    && (vehicleDraft.status !== 'active' || vehicleDraft.brandId),
))


/** 比较品牌编辑区与当前服务端基线；新增弹窗只有真正输入后才算未保存。 */
const brandDraftDirty = computed(() => {
  if (brandCreateOpen.value) {
    return Boolean(
      brandDraft.displayName.trim()
      || brandDraft.aliases.trim()
      || brandDraft.role !== 'owned'
      || brandDraft.status !== 'active',
    )
  }
  const current = selectedBrand.value
  if (!current) return false
  return brandDraft.displayName.trim() !== current.display_name
    || brandDraft.role !== current.role
    || brandDraft.status !== current.status
    || JSON.stringify(splitLines(brandDraft.aliases)) !== JSON.stringify(
      (current.aliases ?? []).map((alias) => alias.text),
    )
})

/** 车型弹窗只有在打开时参与离开保护，并与当前车型或新增默认值比较。 */
const vehicleDraftDirty = computed(() => {
  if (!vehicleEditorOpen.value) return false
  const current = vehicles.value.find((item) => item.id === vehicleDraft.id)
  if (!current) {
    return Boolean(
      vehicleDraft.displayName.trim()
      || vehicleDraft.seriesName.trim()
      || vehicleDraft.aliases.trim()
      || vehicleDraft.status !== 'active'
      || vehicleDraft.brandId !== selectedBrandId.value
      || mergeTargetId.value,
    )
  }
  return vehicleDraft.displayName.trim() !== current.display_name
    || vehicleDraft.brandId !== (current.brand_id ?? '')
    || vehicleDraft.seriesName.trim() !== (current.series_name ?? '')
    || vehicleDraft.status !== (current.status === 'deprecated' ? 'deprecated' : 'active')
    || JSON.stringify(splitLines(vehicleDraft.aliases)) !== JSON.stringify(
      (current.aliases ?? []).map((alias) => alias.text),
    )
    || Boolean(mergeTargetId.value)
})

const navigationDirty = computed(() => brandDraftDirty.value || vehicleDraftDirty.value)

/** 将目录编辑草稿状态上送给管理员 Page Owner。 */
watch(navigationDirty, (dirty) => emit('dirty-change', dirty), { immediate: true })

onMounted(load)

/** 品牌与车型属于同一目录视图，首次进入时并行恢复两类事实。 */
async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [vehicleResponse, brandResponse] = await Promise.all([
      fetchVehicles(),
      fetchVehicleBrandsForAdmin(),
    ])
    vehicles.value = vehicleResponse.items
    brands.value = brandResponse.items
    const selected = brands.value.find((item) => item.id === selectedBrandId.value) ?? brands.value[0]
    if (selected) selectBrand(selected)
    else clearBrandDraft()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    loading.value = false
  }
}

/** 将文本输入收敛成去重后的非空识别词集合。 */
function splitLines(value: string): string[] {
  return [...new Set(value.split(/[\n,，]/).map((item) => item.trim()).filter(Boolean))]
}

/** 目录为空时清空品牌与车型草稿。 */
function clearBrandDraft(): void {
  selectedBrandId.value = ''
  Object.assign(brandDraft, {
    id: '', displayName: '', role: 'owned', aliases: '', status: 'active',
  })
  resetVehicleDraft()
}

/** 选中品牌后把服务端事实同步到右侧详情。 */
function selectBrand(item: BrandResponse): void {
  selectedBrandId.value = item.id
  Object.assign(brandDraft, {
    id: item.id,
    displayName: item.display_name,
    role: item.role,
    aliases: (item.aliases ?? []).map((alias) => alias.text).join('\n'),
    status: item.status,
  })
  resetVehicleDraft(item.id)
}

/** 打开新增品牌弹窗，不改变背景当前选择。 */
function openBrandCreateDialog(): void {
  Object.assign(brandDraft, {
    id: '', displayName: '', role: 'owned', aliases: '', status: 'active',
  })
  brandCreateOpen.value = true
}

/** 取消新增品牌后恢复当前选中品牌详情。 */
function closeBrandCreateDialog(): void {
  brandCreateOpen.value = false
  const current = selectedBrand.value
  if (current) selectBrand(current)
}

/** 放弃当前品牌详情中的未保存输入。 */
function cancelBrandChanges(): void {
  const current = selectedBrand.value
  if (current) selectBrand(current)
}

/** 品牌基础字段与识别词继续分别经过当前正式 API。 */
async function saveBrand(): Promise<void> {
  if (!brandFormValid.value || saving.value) return
  const creating = !brandDraft.id
  saving.value = true
  error.value = null
  notice.value = null
  try {
    const requestedAliases = splitLines(brandDraft.aliases)
    let brandId = brandDraft.id
    if (!brandId) {
      const created = await addBrand({
        display_name: brandDraft.displayName.trim(),
        role: brandDraft.role,
        aliases: requestedAliases,
      })
      brandId = created.id
    } else {
      const current = brands.value.find((item) => item.id === brandId)
      await editBrand(brandId, {
        display_name: brandDraft.displayName.trim(),
        role: brandDraft.role,
        status: brandDraft.status,
      })
      const currentAliases = current?.aliases ?? []
      const requested = new Set(requestedAliases)
      await Promise.all(
        currentAliases
          .filter((alias) => !requested.has(alias.text))
          .map((alias) => removeBrandAlias(brandId, alias.id)),
      )
      const existing = new Set(currentAliases.map((alias) => alias.text))
      await Promise.all(
        requestedAliases
          .filter((text) => !existing.has(text))
          .map((text) => addBrandAlias(brandId, { text })),
      )
    }
    selectedBrandId.value = brandId
    brandCreateOpen.value = false
    notice.value = creating ? '品牌已创建并记录操作。' : '品牌与识别词已更新并记录操作。'
    await load()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

/** 目录行快捷启停只修改品牌状态，不复制别名或车型规则。 */
async function setBrandStatus(item: BrandResponse, status: 'active' | 'deprecated'): Promise<void> {
  if (saving.value || item.status === status) return
  saving.value = true
  error.value = null
  notice.value = null
  try {
    await editBrand(item.id, {
      display_name: item.display_name,
      role: item.role,
      status,
    })
    selectedBrandId.value = item.id
    notice.value = status === 'active' ? '品牌已启用并记录操作。' : '品牌已停用并记录操作。'
    await load()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

/** 删除品牌先进入确认层；真正删除资格继续由后端守卫。 */
function requestDeleteBrand(item: BrandResponse): void {
  resourceConflict.value = null
  brandDeleteTarget.value = item
}

/** 服务端拒绝删除时展示冲突状态，不伪造成功。 */
async function confirmDeleteBrand(): Promise<void> {
  const item = brandDeleteTarget.value
  if (!item || saving.value) return
  saving.value = true
  error.value = null
  try {
    await removeBrand(item.id)
    brandDeleteTarget.value = null
    selectedBrandId.value = ''
    notice.value = '未引用品牌已删除并记录操作。'
    await load()
  } catch (reason) {
    brandDeleteTarget.value = null
    resourceConflict.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

/** 新车型默认继承当前品牌；内部编码由服务端创建时生成。 */
function resetVehicleDraft(brandId = selectedBrandId.value): void {
  Object.assign(vehicleDraft, {
    id: '', displayName: '', brandId, seriesName: '', aliases: '', status: 'active',
  })
  mergeTargetId.value = ''
}

/** 把车型服务端事实同步进编辑弹窗。 */
function editVehicleDraft(item: VehicleModelResponse): void {
  Object.assign(vehicleDraft, {
    id: item.id,
    displayName: item.display_name,
    brandId: item.brand_id ?? '',
    seriesName: item.series_name ?? '',
    aliases: (item.aliases ?? []).map((alias) => alias.text).join('\n'),
    status: item.status === 'deprecated' ? 'deprecated' : 'active',
  })
  mergeTargetId.value = ''
}

/** 用服务端规范化响应替换或追加车型，避免成功保存后阻塞全目录重读。 */
function upsertVehicle(item: VehicleModelResponse): void {
  const remaining = vehicles.value.filter((vehicle) => vehicle.id !== item.id)
  vehicles.value = [...remaining, item].sort((left, right) => (
    left.display_name.localeCompare(right.display_name) || left.id.localeCompare(right.id)
  ))
}

/** 打开新增车型弹窗。 */
function openNewVehicleDialog(): void {
  resetVehicleDraft(selectedBrandId.value)
  vehicleEditorOpen.value = true
}

/** 打开车型编辑弹窗。 */
function openVehicleEditor(item: VehicleModelResponse): void {
  editVehicleDraft(item)
  vehicleEditorOpen.value = true
}

/** 保存车型；品牌归属继续只通过 Vehicle API 修改。 */
async function saveVehicle(): Promise<void> {
  if (!vehicleFormValid.value || saving.value) return
  const editing = Boolean(vehicleDraft.id)
  saving.value = true
  error.value = null
  notice.value = null
  try {
    let saved: VehicleModelResponse
    if (vehicleDraft.id) {
      saved = await editVehicle(vehicleDraft.id, {
        display_name: vehicleDraft.displayName.trim(),
        brand_id: vehicleDraft.brandId || null,
        series_name: vehicleDraft.seriesName.trim() || null,
        aliases: splitLines(vehicleDraft.aliases),
        status: vehicleDraft.status,
      })
    } else {
      saved = await addVehicle({
        display_name: vehicleDraft.displayName.trim(),
        brand_id: vehicleDraft.brandId,
        series_name: vehicleDraft.seriesName.trim() || null,
        aliases: splitLines(vehicleDraft.aliases),
      })
    }
    upsertVehicle(saved)
    vehicleEditorOpen.value = false
    notice.value = editing ? '车型已更新并记录操作。' : '车型已创建并记录操作。'
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

/** 已引用车型直接进入不可删除状态；未引用车型进入确认层。 */
function requestDeleteVehicle(item: VehicleModelResponse): void {
  if (item.referenced) {
    resourceConflict.value = '该车型已被业务数据引用，不能直接删除；请停用、改名或合并。'
    return
  }
  resourceConflict.value = null
  vehicleDeleteTarget.value = item
}

/** 从当前编辑弹窗发起删除请求。 */
function requestCurrentVehicleDelete(): void {
  const item = vehicles.value.find((entry) => entry.id === vehicleDraft.id)
  if (item) requestDeleteVehicle(item)
}

/** 删除未引用车型；最终资格仍以服务端响应为准。 */
async function confirmDeleteVehicle(): Promise<void> {
  const item = vehicleDeleteTarget.value
  if (!item || saving.value) return
  saving.value = true
  error.value = null
  notice.value = null
  try {
    await removeVehicle(item.id)
    vehicleDeleteTarget.value = null
    vehicleEditorOpen.value = false
    notice.value = '未引用车型已删除并记录操作。'
    await load()
  } catch (reason) {
    vehicleDeleteTarget.value = null
    resourceConflict.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}

/** 合并只提交目标车型身份，历史保留与引用更新由后端负责。 */
async function mergeSelectedVehicle(): Promise<void> {
  if (saving.value || !vehicleDraft.id || !mergeTargetId.value) return
  if (!window.confirm('合并后历史数据仍会保留，后续选择会统一到目标车型。是否继续？')) return
  saving.value = true
  error.value = null
  notice.value = null
  try {
    await mergeVehicle(vehicleDraft.id, { target_vehicle_model_id: mergeTargetId.value })
    vehicleEditorOpen.value = false
    notice.value = '车型已合并并记录操作。'
    await load()
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <fieldset
    class="catalog-panel"
    :disabled="saving"
    aria-label="品牌与车型"
  >
    <AimaFeedbackBanner
      v-if="error"
      tone="error"
      role="alert"
    >
      <strong>品牌与车型加载或保存失败</strong>
      <span>{{ error }}</span>
      <AimaButton
        v-if="!saving"
        variant="text"
        size="small"
        @click="load"
      >
        重试
      </AimaButton>
    </AimaFeedbackBanner>
    <AimaFeedbackBanner
      v-if="notice"
      tone="success"
    >
      {{ notice }}
    </AimaFeedbackBanner>

    <div
      v-if="loading"
      class="state-card"
    >
      正在加载品牌与车型…
    </div>

    <div
      v-else
      class="two-column brand-overview"
    >
      <section class="card brand-directory-card">
        <header>
          <div>
            <h2>品牌目录</h2>
            <p>内部品牌编码由服务端生成并仅用于技术识别；品牌识别词用于统一匹配，旗下车型通过唯一品牌归属自动纳入过滤。</p>
          </div>
          <AimaButton
            variant="primary"
            size="small"
            :disabled="saving"
            @click="openBrandCreateDialog"
          >
            新增品牌
          </AimaButton>
        </header>

        <div
          class="admin-table-scroll brand-directory-viewport"
          role="region"
          aria-label="品牌目录表格"
          tabindex="0"
        >
          <table class="brand-directory-table">
            <colgroup>
              <col class="brand-col-name">
              <col class="brand-col-aliases">
              <col class="brand-col-status">
              <col class="brand-col-count">
              <col class="brand-col-actions">
            </colgroup>
            <thead>
              <tr>
                <th>品牌</th>
                <th>识别词</th>
                <th>状态</th>
                <th>车型</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in brands"
                :key="item.id"
                :class="{ selected: selectedBrandId === item.id }"
              >
                <td>
                  <button
                    type="button"
                    class="brand-name-button"
                    @click="selectBrand(item)"
                  >
                    <strong>{{ item.display_name }}</strong>
                    <small>{{ item.role === 'owned' ? '自有品牌' : item.role === 'competitor' ? '竞品' : '其他品牌' }}</small>
                  </button>
                </td>
                <td>{{ (item.aliases ?? []).map((alias) => alias.text).join('、') || '—' }}</td>
                <td>
                  <span
                    class="status-text"
                    :class="{ muted: item.status !== 'active' }"
                  >
                    {{ item.status === 'active' ? '已启用' : '停用' }}
                  </span>
                </td>
                <td>{{ vehicles.filter((vehicle) => vehicle.brand_id === item.id).length }} 个</td>
                <td class="table-actions">
                  <button
                    type="button"
                    @click="selectBrand(item)"
                  >
                    编辑
                  </button>
                  <button
                    v-if="item.status === 'active'"
                    type="button"
                    @click="setBrandStatus(item, 'deprecated')"
                  >
                    停用
                  </button>
                  <button
                    v-else
                    type="button"
                    @click="setBrandStatus(item, 'active')"
                  >
                    启用
                  </button>
                  <button
                    type="button"
                    @click="requestDeleteBrand(item)"
                  >
                    删除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p
          v-if="brands.length === 0"
          class="empty-state"
        >
          暂无品牌，请先新增品牌。
        </p>

        <AimaFeedbackBanner
          v-if="brands.length > 0"
          tone="warning"
        >
          已被车型或历史内容引用的品牌不能物理删除；请停用或改名，历史证据继续保留。
        </AimaFeedbackBanner>
      </section>

      <section
        v-if="selectedBrand"
        class="card form-card brand-detail-card"
      >
        <header class="brand-detail-header">
          <h2>品牌详情</h2>
          <div class="brand-detail-actions">
            <AimaButton
              size="small"
              @click="cancelBrandChanges"
            >
              取消
            </AimaButton>
            <AimaButton
              variant="primary"
              size="small"
              aria-label="保存品牌"
              :disabled="saving || !brandFormValid"
              @click="saveBrand"
            >
              保存
            </AimaButton>
          </div>
        </header>

        <label>
          品牌名称
          <input
            v-model="brandDraft.displayName"
            maxlength="200"
            aria-label="显示名称"
          >
        </label>
        <label>
          品牌角色
          <select v-model="brandDraft.role">
            <option value="owned">
              自有品牌
            </option>
            <option value="competitor">
              竞品品牌
            </option>
            <option value="other">
              其他品牌
            </option>
          </select>
        </label>
        <label>
          品牌识别词（每行一个）
          <textarea
            v-model="brandDraft.aliases"
            rows="4"
          />
        </label>

        <fieldset class="status-field">
          <legend>状态</legend>
          <label class="radio-option">
            <input
              v-model="brandDraft.status"
              type="radio"
              value="active"
            >
            <span>已启用</span>
          </label>
          <label class="radio-option">
            <input
              v-model="brandDraft.status"
              type="radio"
              value="deprecated"
            >
            <span>停用</span>
          </label>
        </fieldset>

        <hr>

        <div class="vehicle-summary-header">
          <h3>旗下车型</h3>
          <span>{{ selectedBrandVehicles.length }}个车型</span>
        </div>

        <div
          class="list-card vehicle-compact-list admin-table-scroll"
          role="region"
          aria-label="车型目录表格"
          tabindex="0"
        >
          <table>
            <thead>
              <tr>
                <th>系列</th>
                <th>车型</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in selectedBrandVehicles"
                :key="item.id"
              >
                <td>{{ item.series_name || '—' }}</td>
                <td>
                  <strong>{{ item.display_name }}</strong>
                </td>
                <td>
                  <span
                    class="vehicle-status"
                    :class="{ muted: item.status !== 'active' }"
                  >
                    {{ item.status === 'active' ? '启用' : formatRuntimeStatus(item.status) }}
                  </span>
                </td>
                <td>
                  <button
                    type="button"
                    @click="openVehicleEditor(item)"
                  >
                    编辑
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p
          v-if="selectedBrandVehicles.length === 0"
          class="empty-state compact"
        >
          当前品牌暂无车型。
        </p>

        <div class="vehicle-toolbar">
          <span />
          <AimaButton
            variant="primary"
            size="small"
            :disabled="saving"
            @click="openNewVehicleDialog"
          >
            新增车型
          </AimaButton>
        </div>

        <details class="technical-details brand-technical">
          <summary>技术信息</summary>
          <dl>
            <div>
              <dt>品牌编码</dt>
              <dd>{{ selectedBrand.code }}</dd>
            </div>
            <div>
              <dt>目录版本</dt>
              <dd>v{{ selectedBrand.catalog_version }}</dd>
            </div>
          </dl>
        </details>
      </section>

      <section
        v-else
        class="card form-card brand-detail-card empty-detail"
      >
        <h2>品牌详情</h2>
        <p>请选择品牌，或新增品牌后继续配置旗下车型。</p>
      </section>
    </div>

    <AimaDialog
      v-model="brandCreateOpen"
      label="新增品牌"
      width="420px"
      @update:model-value="(open) => { if (!open) closeBrandCreateDialog() }"
    >
      <section class="resource-dialog-form">
        <h2>新增品牌</h2>
        <label>
          品牌名称
          <input
            v-model="brandDraft.displayName"
            maxlength="200"
            placeholder="请输入品牌名称"
          >
        </label>
        <label>
          品牌角色
          <select v-model="brandDraft.role">
            <option value="owned">
              自有品牌
            </option>
            <option value="competitor">
              竞品品牌
            </option>
            <option value="other">
              其他品牌
            </option>
          </select>
        </label>
        <label>
          品牌识别词（每行一个）
          <textarea
            v-model="brandDraft.aliases"
            rows="4"
            placeholder="请输入识别词，每行一个"
          />
        </label>
        <div class="creation-status-note">
          <strong>状态</strong>
          <span>新建品牌按当前 Contract 默认启用；内部编码由服务端自动生成，创建后可在品牌详情中停用。</span>
        </div>
        <div class="actions">
          <AimaButton @click="closeBrandCreateDialog">
            取消
          </AimaButton>
          <AimaButton
            variant="primary"
            :disabled="saving || !brandFormValid"
            @click="saveBrand"
          >
            创建品牌
          </AimaButton>
        </div>
      </section>
    </AimaDialog>

    <AimaDialog
      v-model="vehicleEditorOpen"
      :label="vehicleDraft.id ? '编辑车型' : '新增车型'"
      width="420px"
    >
      <section class="resource-dialog-form vehicle-dialog-form">
        <h2>{{ vehicleDraft.id ? '编辑车型' : '新增车型' }}</h2>
        <label>
          车型名称
          <input
            v-model="vehicleDraft.displayName"
            maxlength="200"
            placeholder="例如 爱玛 Q7"
          >
        </label>
        <label>
          品牌
          <select
            v-model="vehicleDraft.brandId"
            aria-label="品牌"
          >
            <option value="">
              请选择品牌
            </option>
            <option
              v-for="brand in brands"
              :key="brand.id"
              :value="brand.id"
            >
              {{ brand.display_name }}
            </option>
          </select>
          <small>active 车型必须显式绑定一个当前可用品牌；修改归属只通过 Vehicle API。</small>
        </label>
        <label>
          系列（可选）
          <input
            v-model="vehicleDraft.seriesName"
            maxlength="200"
            placeholder="用于车型筛选分组"
          >
        </label>
        <label>
          别名（每行一个）
          <textarea
            v-model="vehicleDraft.aliases"
            rows="4"
            placeholder="Q7&#10;爱玛Q7"
          />
        </label>

        <fieldset
          v-if="vehicleDraft.id"
          class="status-field"
        >
          <legend>状态</legend>
          <label class="radio-option">
            <input
              v-model="vehicleDraft.status"
              type="radio"
              value="active"
            >
            <span>已启用</span>
          </label>
          <label class="radio-option">
            <input
              v-model="vehicleDraft.status"
              type="radio"
              value="deprecated"
            >
            <span>停用</span>
          </label>
        </fieldset>
        <div
          v-else
          class="creation-status-note"
        >
          <strong>状态</strong>
          <span>新建车型按当前 Contract 默认启用；内部编码由服务端自动生成，创建后可在编辑车型中停用。</span>
        </div>

        <details
          v-if="vehicleDraft.id"
          class="merge-vehicle-details"
        >
          <summary>合并重复车型</summary>
          <select v-model="mergeTargetId">
            <option value="">
              选择目标车型
            </option>
            <option
              v-for="item in vehicles.filter((vehicle) => vehicle.id !== vehicleDraft.id && vehicle.status === 'active')"
              :key="item.id"
              :value="item.id"
            >
              {{ item.display_name }}
            </option>
          </select>
          <AimaButton
            size="small"
            :disabled="!mergeTargetId"
            @click="mergeSelectedVehicle"
          >
            合并到目标车型
          </AimaButton>
        </details>

        <div class="actions">
          <AimaButton @click="vehicleEditorOpen = false">
            取消
          </AimaButton>
          <AimaButton
            v-if="vehicleDraft.id"
            variant="text"
            @click="requestCurrentVehicleDelete"
          >
            删除
          </AimaButton>
          <AimaButton
            variant="primary"
            :disabled="saving || !vehicleFormValid"
            @click="saveVehicle"
          >
            保存
          </AimaButton>
        </div>
      </section>
    </AimaDialog>

    <AimaDialog
      :model-value="Boolean(brandDeleteTarget)"
      label="删除品牌"
      width="420px"
      @update:model-value="(open) => { if (!open) brandDeleteTarget = null }"
    >
      <section class="confirm-dialog">
        <h2>删除品牌</h2>
        <p>确定删除未被引用的品牌“{{ brandDeleteTarget?.display_name }}”吗？服务端会拒绝删除仍有关联的品牌。</p>
        <div class="actions">
          <AimaButton @click="brandDeleteTarget = null">
            取消
          </AimaButton>
          <AimaButton
            variant="primary"
            @click="confirmDeleteBrand"
          >
            确认删除
          </AimaButton>
        </div>
      </section>
    </AimaDialog>

    <AimaDialog
      :model-value="Boolean(vehicleDeleteTarget)"
      label="删除车型"
      width="420px"
      @update:model-value="(open) => { if (!open) vehicleDeleteTarget = null }"
    >
      <section class="confirm-dialog">
        <h2>删除车型</h2>
        <p>确定删除未引用车型“{{ vehicleDeleteTarget?.display_name }}”吗？系统会保留本次操作记录。</p>
        <div class="actions">
          <AimaButton @click="vehicleDeleteTarget = null">
            取消
          </AimaButton>
          <AimaButton
            variant="primary"
            @click="confirmDeleteVehicle"
          >
            确认删除
          </AimaButton>
        </div>
      </section>
    </AimaDialog>

    <AimaDialog
      :model-value="Boolean(resourceConflict)"
      label="当前资源无法删除"
      width="420px"
      @update:model-value="(open) => { if (!open) resourceConflict = null }"
    >
      <section class="confirm-dialog conflict-dialog">
        <h2>当前资源无法删除</h2>
        <p>{{ resourceConflict }}</p>
        <div class="actions">
          <AimaButton
            variant="primary"
            @click="resourceConflict = null"
          >
            知道了
          </AimaButton>
        </div>
      </section>
    </AimaDialog>
  </fieldset>
</template>

<style scoped>
.catalog-panel { display: grid; margin: 0; padding: 0; border: 0; gap: 16px; min-width: 0; }
.state-card,
.card { min-width: 0; padding: 16px; border: 1px solid var(--aima-border); border-radius: 8px; background: var(--aima-surface); }
.state-card { color: var(--aima-text-muted); text-align: center; }
.two-column { display: grid; grid-template-columns: minmax(620px, 2fr) minmax(360px, 398px); align-items: start; gap: 24px; min-width: 0; }
.brand-directory-card,
.brand-detail-card { height: min(692px, calc(100dvh - 184px)); min-height: 420px; overflow-y: auto; }
.card > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
h2, h3, p { margin: 0; }
h2 { color: var(--aima-text); font-size: 16px; font-weight: 500; line-height: 24px; }
h3 { color: var(--aima-text); font-size: 13px; font-weight: 500; line-height: 20px; }
.card p { margin-top: 4px; color: var(--aima-text-muted); font-size: 11px; line-height: 16px; }
.admin-table-scroll { min-width: 0; max-width: 100%; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; color: var(--aima-text-secondary); font-size: 13px; line-height: 20px; }
.brand-directory-table { min-width: 726px; table-layout: fixed; }
.brand-col-name { width: 190px; }
.brand-col-aliases { width: auto; }
.brand-col-status { width: 80px; }
.brand-col-count { width: 80px; }
.brand-col-actions { width: 124px; }
.brand-directory-table thead tr { height: 40px; }
.brand-directory-table tbody tr { height: 72px; }
.brand-directory-table tbody tr.selected { background: #fff9fc; }
.brand-directory-table th,
.brand-directory-table td { padding: 10px 8px; border-bottom: 1px solid var(--aima-border); text-align: center; vertical-align: middle; }
.brand-directory-table th { color: var(--aima-text-muted); background: #fafbfc; font-size: 12px; font-weight: 500; }
.brand-name-button { display: grid; width: 100%; gap: 4px; border: 0; color: inherit; background: transparent; cursor: pointer; text-align: center; }
.brand-name-button strong { color: var(--aima-text); font-size: 14px; font-weight: 700; }
.brand-name-button small { color: var(--aima-text-muted); font-size: 12px; }
.status-text { color: var(--aima-color-success, #12b76a); }
.status-text.muted { color: var(--aima-text-disabled); }
.table-actions { white-space: nowrap; }
.table-actions button,
.vehicle-compact-list td button { margin: 0 4px; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 12px; }
.brand-directory-card :deep(.aima-feedback-banner) { margin-top: 16px; }
.form-card { display: grid; align-content: start; gap: 12px; }
.form-card label,
.resource-dialog-form > label { display: grid; gap: 6px; color: var(--aima-text-tertiary, #a8b0bf); font-size: 11px; line-height: 16px; }
.form-card label > small,
.resource-dialog-form label > small { color: var(--aima-text-disabled); font-size: 10px; line-height: 15px; }
input, textarea, select { width: 100%; box-sizing: border-box; padding: 8px 12px; border: 1px solid var(--aima-border-strong); border-radius: 8px; outline: none; color: var(--aima-text); background: var(--aima-surface); font: inherit; font-size: 13px; line-height: 20px; }
input, select { height: 40px; }
textarea { min-height: 88px; resize: vertical; }
input:focus, textarea:focus, select:focus { border-color: var(--aima-primary); box-shadow: 0 0 0 2px var(--aima-primary-soft); }
input:read-only, input:disabled { cursor: not-allowed; color: var(--aima-text-disabled); background: var(--aima-color-bg-disabled, #f2f5f7); }
.brand-detail-header { align-items: center !important; }
.brand-detail-actions { display: flex; gap: 8px; }
.status-field { display: flex; width: fit-content; margin: 0; padding: 10px 16px; gap: 16px; border: 1px solid var(--aima-border); border-radius: 8px; }
.status-field legend { margin-bottom: 6px; padding: 0; color: var(--aima-text-tertiary, #a8b0bf); font-size: 11px; }
.radio-option { display: inline-flex !important; align-items: center; gap: 6px !important; color: var(--aima-text) !important; font-size: 13px !important; }
.radio-option input { width: 14px; height: 14px; accent-color: var(--aima-primary); }
hr { width: 100%; margin: 0; border: 0; border-top: 1px solid var(--aima-border); }
.vehicle-summary-header,
.vehicle-toolbar { display: flex; align-items: center; justify-content: space-between; }
.vehicle-summary-header > span { padding: 2px 8px; border-radius: 999px; color: var(--aima-text-muted); background: var(--aima-color-bg-disabled, #f2f5f7); font-size: 11px; }
.vehicle-compact-list { border: 1px solid var(--aima-border); border-radius: 8px; }
.vehicle-compact-list table { min-width: 726px; table-layout: fixed; }
.vehicle-compact-list th:nth-child(1) { width: 120px; }
.vehicle-compact-list th:nth-child(3) { width: 90px; }
.vehicle-compact-list th:nth-child(4) { width: 80px; }
.vehicle-compact-list th,
.vehicle-compact-list td { padding: 8px 12px; border-bottom: 1px solid var(--aima-border); text-align: left; vertical-align: middle; }
.vehicle-compact-list th { color: var(--aima-text-muted); background: var(--aima-color-bg-disabled, #f2f5f7); font-size: 11px; font-weight: 500; }
.vehicle-compact-list td { font-size: 12px; }
.vehicle-compact-list td strong,
.vehicle-compact-list td small { display: block; }
.vehicle-compact-list td small { margin-top: 2px; color: var(--aima-text-muted); font-size: 10px; }
.vehicle-status { display: inline-flex; padding: 2px 8px; border-radius: 999px; color: #1f9d55; background: #e8f5ee; }
.vehicle-status.muted { color: var(--aima-text-muted); background: var(--aima-color-bg-disabled, #f2f5f7); }
.empty-state { padding: 20px 10px; color: var(--aima-text-muted); font-size: 12px; }
.empty-state.compact { padding: 8px 0; }
.empty-detail { min-height: 180px; height: auto; }
.actions { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.technical-details { border: 1px solid var(--aima-border); border-radius: 7px; padding: 10px 12px; }
.technical-details summary { cursor: pointer; color: var(--aima-text-secondary); font-size: 11px; font-weight: 600; }
.technical-details dl { display: grid; gap: 7px; margin: 10px 0 0; }
.technical-details dl div { display: grid; grid-template-columns: 100px minmax(0, 1fr); gap: 8px; }
.technical-details dt { color: var(--aima-text-disabled); font-size: 10px; }
.technical-details dd { margin: 0; overflow-wrap: anywhere; color: var(--aima-text-secondary); font-size: 11px; }
.brand-technical { margin-top: 4px; }
.resource-dialog-form,
.confirm-dialog { display: grid; gap: 12px; padding: 20px 24px 16px; }
.resource-dialog-form > h2,
.confirm-dialog > h2 { padding-bottom: 10px; border-bottom: 1px solid var(--aima-border); font-size: 15px; font-weight: 700; }
.vehicle-dialog-form { max-height: min(760px, calc(100dvh - 72px)); overflow-y: auto; }
.creation-status-note { display: grid; gap: 4px; padding: 10px 12px; border: 1px solid var(--aima-border); border-radius: 8px; color: var(--aima-text-secondary); background: #fbfcfe; font-size: 11px; line-height: 16px; }
.creation-status-note strong { color: var(--aima-text); }
.merge-vehicle-details { border: 1px solid var(--aima-border); border-radius: 8px; padding: 10px 12px; }
.merge-vehicle-details summary { cursor: pointer; color: var(--aima-text-secondary); font-size: 11px; font-weight: 600; }
.merge-vehicle-details select { margin: 10px 0; }
.confirm-dialog > p { color: var(--aima-text-secondary); font-size: 13px; line-height: 20px; }
.conflict-dialog > p { color: var(--aima-color-danger, #d92d20); }

@media (max-width: 1439px) {
  .two-column { grid-template-columns: 1fr; }
  .brand-directory-card,
  .brand-detail-card { width: 100%; height: auto; min-height: 0; max-height: none; }
}
@media (min-width: 1600px) {
  .two-column { grid-template-columns: minmax(720px, 1fr) 398px; }
}
</style>
