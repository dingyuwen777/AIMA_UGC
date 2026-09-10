import { expect, type APIRequestContext } from '@playwright/test'
import { randomUUID } from 'node:crypto'

interface BrandListItem {
  id: string
  display_name: string
  aliases: Array<{ text: string }>
}

export interface Stage3FilterBrand {
  id: string
  name: string
}

/** 复用已有识别词，或建立供真实全栈导入使用的启用品牌。 */
export async function ensureStage3FilterBrand(
  request: APIRequestContext,
  alias = '爱玛',
): Promise<Stage3FilterBrand> {
  const listed = await request.get('/api/v1/vehicle-brands', {
    params: { status: 'active', offset: 0, limit: 200 },
  })
  expect(listed.status()).toBe(200)
  const body = await listed.json() as { items: BrandListItem[] }
  const existing = body.items.find(
    (item) => item.display_name === alias || item.aliases.some((candidate) => candidate.text === alias),
  )
  if (existing) return { id: existing.id, name: existing.display_name }

  const created = await request.post('/api/v1/vehicle-brands', {
    data: {
      code: `FS-STAGE3-${randomUUID()}`,
      display_name: alias,
      role: 'owned',
      aliases: [alias],
    },
  })
  expect(created.status()).toBe(201)
  const brand = await created.json() as BrandListItem
  return { id: brand.id, name: brand.display_name }
}
