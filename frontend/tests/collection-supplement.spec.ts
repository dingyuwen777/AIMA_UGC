import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref, type EffectScope } from 'vue'
import { flushPromises } from '@vue/test-utils'
import type { CollectionSupplementPreviewResponse, CollectionSupplementTargetSelection } from '../src/generated/api/client'
import { AimaApiError } from '../src/shared/api/http'
import * as api from '../src/features/collection-supplement/api'
import { useCollectionSupplement } from '../src/features/collection-supplement/useCollectionSupplement'
vi.mock('../src/features/collection-supplement/api', () => ({
  previewSupplement: vi.fn(), createSupplement: vi.fn(), fetchSupplementCapabilities: vi.fn(),
}))
const mocked = vi.mocked(api)
const scopes: EffectScope[] = []
const a: CollectionSupplementTargetSelection = { kind: 'published_date_range', published_from: '2026-09-01T00:00:00+08:00', published_to: '2026-09-01T23:59:59+08:00' }
function result(count = 2): CollectionSupplementPreviewResponse {
  return { target_count: count, target_fingerprint: 'a'.repeat(64), platforms: count ? [{ platform: 'douyin', content_count: count, direct_target_count: count - 1, resolution_candidate_count: 0, blocked_count: 1, block_reasons: { identity_unavailable: 1 } }] : [] }
}
function setup(selection: CollectionSupplementTargetSelection = a) {
  const scope = effectScope(); scopes.push(scope)
  const active = ref(true)
  const targets = ref<CollectionSupplementTargetSelection | null>(selection)
  const state = scope.run(() => useCollectionSupplement(active, targets))!
  return { active, targets, state }
}
beforeEach(() => {
  vi.resetAllMocks()
  mocked.previewSupplement.mockResolvedValue(result())
  mocked.fetchSupplementCapabilities.mockResolvedValue({ provider_configs: [{ id: 'provider', provider: 'tikhub', display_name: '测试渠道' }], capabilities: [{ platform: 'douyin', provider: 'tikhub', operations: ['content_detail', 'comments', 'sub_comments'], search: null }] })
})
afterEach(() => { scopes.forEach((scope) => scope.stop()); scopes.length = 0 })
describe('shared content supplement', () => {
  it('reopening a selected-content dialog cannot invalidate the only in-flight preview', async () => {
    const { state, active } = setup({ kind: 'selected', content_ids: ['id-1'] })
    await flushPromises()
    active.value = false; await nextTick()
    active.value = true; await flushPromises()
    expect(state.loading).toBe(false)
    expect(state.preview?.target_count).toBe(2)
    expect(state.canSubmit).toBe(true)
  })
  it('loads generated preview, binds selected platform and options before creation', async () => {
    const { state } = setup(); await flushPromises()
    expect(state.canSubmit).toBe(false)
    state.togglePlatform('douyin'); await flushPromises()
    expect(state.canSubmit).toBe(true)
    expect(state.preview?.target_count).toBe(2)
    await state.create()
    expect(mocked.createSupplement).toHaveBeenCalledWith(expect.objectContaining({ mode: 'content_supplement', supplement_targets: a, expected_target_count: 2, expected_target_fingerprint: 'a'.repeat(64), platforms: [{ platform: 'douyin', provider_config_id: 'provider' }] }))
  })
  it('ignores stale A to B to A and close/reopen responses', async () => {
    const deferred: ((value: CollectionSupplementPreviewResponse) => void)[] = []
    mocked.previewSupplement.mockImplementation(() => new Promise((resolve) => deferred.push(resolve)))
    const { state, targets, active } = setup()
    targets.value = { ...a, published_to: '2026-09-02T23:59:59+08:00' }; await nextTick()
    targets.value = { ...a }; await nextTick()
    deferred.at(-1)!(result(3)); await flushPromises()
    deferred[0]!(result(1)); deferred[1]!(result(2)); await flushPromises()
    expect(state.preview?.target_count).toBe(3)
    targets.value = { ...a, published_to: '2026-09-03T23:59:59+08:00' }; await nextTick()
    const last = deferred.at(-1)!
    active.value = false; await nextTick()
    last(result()); await flushPromises()
    expect(state.preview).toBeNull()
    expect(state.canSubmit).toBe(false)
  })
  it('distinguishes preview error from empty selection and recovers', async () => {
    mocked.previewSupplement.mockRejectedValueOnce(new Error('预览失败'))
    const { state } = setup(); await flushPromises()
    expect(state.error).toBe('预览失败'); expect(state.preview).toBeNull()
    mocked.previewSupplement.mockResolvedValueOnce(result(0))
    await state.refreshPreview()
    expect(state.error).toBeNull(); expect(state.preview?.target_count).toBe(0)
    expect(state.canSubmit).toBe(false)
  })
  it('preserves selected platform and blocked identities, fixes comments on and replies off', async () => {
    const { state } = setup({ kind: 'selected', content_ids: ['id-1', 'id-2'] }); await flushPromises()
    expect(state.platforms).toEqual(['douyin'])
    state.togglePlatform('douyin')
    expect(state.platforms).toEqual(['douyin'])
    expect(state.includeComments).toBe(true); expect(state.includeSubComments).toBe(false)
    expect(state.preview?.platforms[0]?.blocked_count).toBe(1)
    expect(state.canSubmit).toBe(true)
    state.providerConfigId = 'unsupported'
    expect(state.canSubmit).toBe(false)
  })
  it('repreviews a 409 and requires another explicit confirmation', async () => {
    const { state } = setup({ kind: 'selected', content_ids: ['id-1'] }); await flushPromises()
    mocked.createSupplement.mockRejectedValueOnce(new AimaApiError({ status: 409, title: 'Conflict', type: 'about:blank', detail: '目标已变', request_id: 'r1', errors: [{ code: 'collection_supplement_targets_changed', message: '目标范围已变化' }] }))
    mocked.previewSupplement.mockResolvedValueOnce(result(3))
    expect(await state.create()).toBeNull()
    expect(mocked.createSupplement).toHaveBeenCalledOnce()
    expect(state.preview?.target_count).toBe(3)
    expect(state.error).toContain('重新确认')
  })
})
