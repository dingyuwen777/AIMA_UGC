import { expect, type Locator, type Page, type TestInfo } from './fixture'

/** 捕获真实滚动区域的普通、鼠标悬停、按下状态，并验证交互不改变几何或宽度。 */
export async function captureScrollbarEvidence(page: Page, target: Locator, info: TestInfo, name: string): Promise<void> {
  const bounds = await target.boundingBox()
  expect(bounds).not.toBeNull()
  const before = await target.evaluate((element) => ({
    overflow: element.scrollHeight > element.clientHeight,
    width: getComputedStyle(element, '::-webkit-scrollbar').width,
    radius: getComputedStyle(element, '::-webkit-scrollbar-thumb').borderRadius,
    track: getComputedStyle(element, '::-webkit-scrollbar-track').backgroundColor,
    clientWidth: element.clientWidth,
  }))
  expect(before.overflow).toBe(true)
  expect(parseFloat(before.width)).toBeGreaterThanOrEqual(3)
  expect(parseFloat(before.width)).toBeLessThanOrEqual(6)
  expect(before.radius).toBe('999px')
  expect(before.track).toBe('rgba(0, 0, 0, 0)')
  await page.mouse.move(1, 1)
  await target.screenshot({ path: info.outputPath(`${name}-normal.png`) })
  await page.mouse.move(bounds!.x + bounds!.width - 2, bounds!.y + 16)
  await target.screenshot({ path: info.outputPath(`${name}-hover.png`) })
  await page.mouse.down()
  await target.screenshot({ path: info.outputPath(`${name}-active.png`) })
  expect(await target.boundingBox()).toEqual(bounds)
  expect(await target.evaluate((element) => ({ width: getComputedStyle(element, '::-webkit-scrollbar').width, clientWidth: element.clientWidth })))
    .toEqual({ width: before.width, clientWidth: before.clientWidth })
  await page.mouse.up()
}
