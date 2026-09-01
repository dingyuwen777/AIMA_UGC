import type { Page } from '@playwright/test'

export const voicePlazaTaxonomyFixture = {
  prompt_version: 'content-labeling.v3',
  prompt_sha256: 'a'.repeat(64),
  schema_version: 'aima-content-taxonomy.v2',
  taxonomy_sha256: 'b'.repeat(64),
  sentiments: ['正面', '中性', '负面'],
  voice_types: ['真实用户发声', '媒体机构发声', '无法判断'],
  labels: [
    { primary_label: '产品体验', secondary_labels: ['续航表现', '通勤体验'] },
    { primary_label: '电池、续航与充电', secondary_labels: ['实际续航表现'] },
    { primary_label: '驾乘体验', secondary_labels: ['坐垫舒适性'] },
    { primary_label: '售后服务', secondary_labels: ['客服与服务态度'] },
  ],
}
/** 为声音广场 Browser Mock 固定来自正式只读 Contract 的分类目录。 */
export async function stubVoicePlazaTaxonomy(page: Page): Promise<void> {
  await page.route('**/api/v1/content-analysis-taxonomy', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(voicePlazaTaxonomyFixture),
    })
  })
}
