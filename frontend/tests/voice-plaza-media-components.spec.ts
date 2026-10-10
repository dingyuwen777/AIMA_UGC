import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { compileScript, parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import { createRenderer, h, nextTick, ref, type Component } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ContentMediaPlaybackResponse, ContentMediaResponse } from '../src/generated/api/client'
import { prepareMediaPlayback } from '../src/features/voice-plaza/api'
import { createMediaPlayback } from '../src/features/voice-plaza/mediaPlayback'

vi.mock('../src/features/voice-plaza/api', () => ({ prepareMediaPlayback: vi.fn() }))

/** 默认 Vitest 为 SSR 编译；这里编译真实 SFC 的客户端模板，以验证更新、事件和 ref 副作用。 */
function clientComponent(file: string): Component {
  const descriptor = parse(readFileSync(file, 'utf8'), { filename: file }).descriptor
  const source = compileScript(descriptor, { id: file, inlineTemplate: true }).content
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module: { exports: { default?: Component } } = { exports: {} }
  const require = (name: string) => {
    if (name === 'vue') return Vue
    if (name.endsWith('.vue')) return { __esModule: true, default: clientComponent(resolve(dirname(file), name)) }
    if (name.endsWith('/mediaPlayback')) return { createMediaPlayback }
    throw new Error(`Unexpected component dependency: ${name}`)
  }
  new Function('require', 'module', 'exports', code)(require, module, module.exports)
  return module.exports.default!
}
const componentRoot = fileURLToPath(new URL('../src/features/voice-plaza/pages/VoicePlazaPage/components/', import.meta.url))
const ContentMediaGallery = clientComponent(resolve(componentRoot, 'ContentMediaGallery.vue'))
const ContentVideoPlayer = clientComponent(resolve(componentRoot, 'ContentVideoPlayer.vue'))

/** 使用 Vue 正式渲染器组合真实组件；仅替代节点与原生媒体副作用，不复制组件状态机。 */
class MediaNode {
  nodes: MediaNode[] = []
  parent: MediaNode | null = null
  props: Record<string, unknown> = {}
  scrollLeft = 0
  error: { code: number } | null = null
  pause = vi.fn()
  load = vi.fn()
  constructor(public tag: string, public text = '') {}
  get children() {
    const children = this.nodes.filter((node) => node.tag !== '#text' && node.tag !== '#comment')
    return Object.assign(children, { item: (index: number) => children[index] ?? null })
  }
  getBoundingClientRect() { return { left: this.parent ? this.parent.children.indexOf(this) * 100 - this.parent.scrollLeft : 0 } }
  scrollTo({ left }: { left: number }) { this.scrollLeft = left }
  removeAttribute(name: string) { delete this.props[name] }
  getAttributeNames() { return Object.keys(this.props) }
  getAttribute(name: string) { return this.props[name] ?? null }
}

const renderer = createRenderer<MediaNode, MediaNode>({
  createElement: (tag) => new MediaNode(tag),
  createText: (text) => new MediaNode('#text', text),
  createComment: (text) => new MediaNode('#comment', text),
  setText: (node, text) => { node.text = text },
  setElementText: (node, text) => { node.nodes = []; node.text = text },
  parentNode: (node) => node.parent,
  nextSibling: (node) => node.parent?.nodes[node.parent.nodes.indexOf(node) + 1] ?? null,
  insert: (node, parent, anchor) => {
    if (node.parent) node.parent.nodes.splice(node.parent.nodes.indexOf(node), 1)
    node.parent = parent
    const index = anchor ? parent.nodes.indexOf(anchor) : -1
    if (index < 0) parent.nodes.push(node)
    else parent.nodes.splice(index, 0, node)
  },
  remove: (node) => { if (node.parent) node.parent.nodes.splice(node.parent.nodes.indexOf(node), 1); node.parent = null },
  patchProp: (node, key, _previous, value) => { node.props[key] = value },
})
const unmount: (() => void)[] = []
const contentId = '10000000-0000-4000-8000-000000000001'
const ready: ContentMediaPlaybackResponse = {
  content_id: contentId, position: 0, status: 'ready', generation: 1, source_revision: 'a'.repeat(64),
  stream_url: `/api/v1/contents/${contentId}/media/0/playback/stream?session=test`,
  job_id: null, cooldown_until: null, failure_code: null,
}

function mount(component: Component, props: () => Record<string, unknown>): MediaNode {
  const root = new MediaNode('root')
  const app = renderer.createApp({ render: () => h(component, props()) })
  app.mount(root)
  unmount.push(() => app.unmount())
  return root
}
function find(node: MediaNode, predicate: (candidate: MediaNode) => boolean): MediaNode | undefined {
  if (predicate(node)) return node
  for (const child of node.nodes) { const match = find(child, predicate); if (match) return match }
  return undefined
}
function byClass(node: MediaNode, name: string) { return find(node, (candidate) => String(candidate.props.class ?? '').split(' ').includes(name))! }
async function fire(node: MediaNode, event: string) { await (node.props[event] as () => unknown)(); await nextTick() }

beforeEach(() => { vi.resetAllMocks(); vi.stubGlobal('HTMLElement', MediaNode) })
afterEach(() => { unmount.splice(0).forEach((close) => close()); vi.unstubAllGlobals() })

describe('媒体画廊与原生播放器组合回归', () => {
  it('画廊显式传递普通用户权限，播放器原生失败不会提交付费恢复', async () => {
    const root = mount(ContentMediaGallery, () => ({ contentId, platform: 'xiaohongshu', contentType: 'video',
      media: [{ position: 0, media_type: 'video' }], open: true, canRecover: false }))
    vi.mocked(prepareMediaPlayback).mockResolvedValue(ready)
    await fire(byClass(root, 'video-prepare'), 'onClick')
    const video = find(root, (node) => node.tag === 'video')!
    video.error = { code: 2 }
    await fire(video, 'onError')
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(1)
    expect(byClass(root, 'video-status').nodes.map((node) => node.text).join('')).not.toContain('恢复一次')
  })
  it('同帖最后一张图片被单个视频完整替换后，视频仍处于可准备状态', async () => {
    const media = ref<ContentMediaResponse[]>([0, 1, 2].map((position) => ({ position, media_type: 'image', preview_url: '/cover' })))
    const root = mount(ContentMediaGallery, () => ({ contentId, platform: 'xiaohongshu', contentType: 'video', media: media.value, open: true, canRecover: true }))
    const grid = byClass(root, 'media-grid')
    grid.scrollLeft = 200
    await fire(grid, 'onScrollPassive')
    media.value = [{ position: 0, media_type: 'video', url: null, preview_url: null }]
    await nextTick()
    await fire(grid, 'onScrollPassive')
    expect(byClass(root, 'video-prepare').props.disabled).toBe(false)
    vi.mocked(prepareMediaPlayback).mockResolvedValue(ready)
    await fire(byClass(root, 'video-prepare'), 'onClick')
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(1)
    expect(find(root, (node) => node.tag === 'video')?.props.src).toBe(ready.stream_url)
  })

  it('同帖媒体重排按仍存在的 position 保留正在播放项，同代次更新不重新准备', async () => {
    const video = { position: 2, media_type: 'video', preview_url: '/cover' }
    const media = ref<ContentMediaResponse[]>([{ position: 0, media_type: 'image' }, { position: 1, media_type: 'image' }, video])
    const root = mount(ContentMediaGallery, () => ({ contentId, platform: 'xiaohongshu', contentType: 'video', media: media.value, open: true, canRecover: true }))
    const grid = byClass(root, 'media-grid')
    grid.scrollLeft = 200
    await fire(grid, 'onScrollPassive')
    const stream = `/api/v1/contents/${contentId}/media/2/playback/stream?session=test`
    vi.mocked(prepareMediaPlayback).mockResolvedValue({ ...ready, position: 2, stream_url: stream })
    await fire(byClass(root, 'video-prepare'), 'onClick')
    const native = find(root, (node) => node.tag === 'video')!
    media.value = [video, { position: 0, media_type: 'image' }]
    await nextTick()
    await nextTick()
    expect(find(root, (node) => node.tag === 'video') === native).toBe(true)
    expect(native.props.src).toBe(stream)
    expect(native.pause).not.toHaveBeenCalled()
    expect(byClass(root, 'media-position').text).toBe('1 / 2')
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(1)
  })

  it('原生 code1 释放后提供显式重试，未点击前不会自动请求恢复', async () => {
    vi.mocked(prepareMediaPlayback).mockResolvedValue(ready)
    const root = mount(ContentVideoPlayer, () => ({ contentId, media: { position: 0, media_type: 'video' }, active: true, canRecover: true }))
    await fire(byClass(root, 'video-prepare'), 'onClick')
    const native = find(root, (node) => node.tag === 'video')!
    native.error = { code: 1 }
    await fire(native, 'onError')
    expect(native.props.src).toBeUndefined()
    expect(native.pause).toHaveBeenCalledTimes(1)
    expect(native.load).toHaveBeenCalledTimes(1)
    expect(Boolean(find(root, (node) => node.tag === 'video'))).toBe(false)
    expect(byClass(root, 'video-prepare').props.disabled).toBe(false)
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(1)
    await fire(byClass(root, 'video-prepare'), 'onClick')
    expect(prepareMediaPlayback).toHaveBeenCalledTimes(2)
    expect(vi.mocked(prepareMediaPlayback).mock.calls[1]![2]).toEqual({})
    expect(find(root, (node) => node.tag === 'video')?.props.src).toBe(ready.stream_url)
  })
})
