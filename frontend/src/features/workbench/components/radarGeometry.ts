export interface RadarLabelBox { label: string; left: number; top: number; width: number; height: number }
export interface RadarGeometry { fontSize: number; radius: number; gap: number; labels: RadarLabelBox[] }

/** 以实际字体宽度搜索可读字号与半径；标签框用于浏览器验收真实裁切和碰撞。 */
export function radarGeometry(
  width: number, height: number, labels: string[], measure: (text: string, fontSize: number) => number,
): RadarGeometry {
  const gap = Math.max(5, Math.min(10, width * 0.018))
  const candidate = (fontSize: number, radius: number, displayed = labels): RadarLabelBox[] => displayed.map((label, index) => {
    const angle = index * Math.PI * 2 / labels.length
    const dx = -Math.sin(angle)
    const dy = -Math.cos(angle)
    const labelWidth = measure(label, fontSize)
    const labelHeight = fontSize + 3
    const x = width / 2 + dx * (radius + gap)
    const y = height / 2 + dy * (radius + gap)
    return { label, left: x - (dx < -0.01 ? labelWidth : dx > 0.01 ? 0 : labelWidth / 2),
      top: y - labelHeight / 2, width: labelWidth, height: labelHeight }
  })
  const valid = (boxes: RadarLabelBox[]): boolean => boxes.every((box, index) =>
    box.left >= 3 && box.top >= 3 && box.left + box.width <= width - 3 && box.top + box.height <= height - 3
    && boxes.slice(index + 1).every((other) => box.left + box.width + 2 <= other.left
      || other.left + other.width + 2 <= box.left || box.top + box.height + 2 <= other.top
      || other.top + other.height + 2 <= box.top),
  )
  for (let fontSize = Math.min(14, Math.max(11, Math.floor(width / 35))); fontSize >= 11; fontSize -= 1) {
    for (let radius = Math.floor(Math.min(width, height) * 0.39); radius >= 24; radius -= 1) {
      const boxes = candidate(fontSize, radius)
      if (valid(boxes)) return { fontSize, radius, gap, labels: boxes }
    }
  }
  // 正常标签已按完整文字搜索到最低可读字号；仅异常长名称保留比例并省略名称。
  for (let budget = Math.floor(width * 0.32); budget >= 35; budget -= 1) {
    const displayed = labels.map((label) => {
      if (measure(label, 11) <= budget) return label
      const split = label.lastIndexOf(' ')
      const suffix = split >= 0 ? label.slice(split) : ''
      const characters = Array.from(split >= 0 ? label.slice(0, split) : label)
      while (characters.length > 0 && measure(`${characters.join('')}…${suffix}`, 11) > budget) characters.pop()
      return `${characters.join('')}…${suffix}`
    })
    for (let radius = Math.floor(Math.min(width, height) * 0.39); radius >= 24; radius -= 1) {
      const boxes = candidate(11, radius, displayed)
      if (valid(boxes)) return { fontSize: 11, radius, gap, labels: boxes }
    }
  }
  const radius = 24
  return { fontSize: 11, radius, gap, labels: candidate(11, radius) }
}
