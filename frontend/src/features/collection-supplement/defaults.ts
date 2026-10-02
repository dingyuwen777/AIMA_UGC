/** 用户主动采集默认读取全部可访问评论；周期计划沿用自身冻结策略。 */
export const manualCommentDefaults = {
  includeComments: true,
  includeSubComments: true,
} as const
