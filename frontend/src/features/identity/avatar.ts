/**
 * 身份区头像的显示判定。
 *
 * 单独放一个 `.ts` 模块（而不是写在 `AppShell.vue` 里）有两个原因：
 * 1. 浏览器里图片加载失败只会触发 `<img>` 的 `error` 事件，而本项目前端单测跑在 node 环境、
 *    没有安装 jsdom/happy-dom，无法真实触发该事件。抽成纯函数后，"失败 → 回退首字"这条
 *    分支才有可执行的证据，而不是只靠读代码相信它写了。
 * 2. `.vue` 的具名导出在 `typecheck:ts7` 的 `*.vue` 类型垫片下不可见，写在这里两个 typecheck 都能过。
 */

/**
 * 决定头像最终要不要用图片地址；返回 `null` 表示应回退到姓名首字。
 *
 * @param rawUrl 后端 `CurrentPrincipalResponse.avatar_url`（可选字段，可能是 null/空串/带空格）
 * @param failed 该地址此前是否已经加载失败（由 `<img>` 的 error 事件置位）
 */
export function resolveAvatarUrl(
  rawUrl: string | null | undefined,
  failed: boolean,
): string | null {
  // 失败标记优先于地址本身：图挂了之后不能把同一个坏地址再交回 <img>，
  // 否则每次重渲染都会重新请求、失败、再回退，界面会闪。
  if (failed) return null
  const trimmed = rawUrl?.trim()
  // 空串/纯空格同样按"没有头像"处理，避免渲染出 src="" 的碎图图标。
  return trimmed ? trimmed : null
}
