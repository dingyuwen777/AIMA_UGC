# PR #662 集中审查记录

## FIRST_ASSEMBLY

- Reviewer：同一位独立 assembly_reviewer。
- 实现 Head：9ff83534f0e00cbd1d86c81ded7a674143431e93。
- Base：da99a65fa94e94b298bb1750cb36e54cf60c8384。
- 结论：BLOCK；8 项稳定编号的 IN_SCOPE/BLOCKING Findings。
- 范围：当前 README AC1–AC8 → Change → 实现/测试/文档；公开账号入口 → 生产 Operation/Mapper → Canonical/Excel → 生产 reader/mapper。
- 证据：独立纯内存生产方法反例、base 兼容比较、diff check 与 DOC003 文档检查；Owner full preflight 是已有证据，没有把 Review 描述成独立重跑全部测试。
- 限制：未发外部 Provider/LLM 请求、未读现有 Secret；XHS 初次反例证明终态传播，未冒充首次公开入口完整纵切。真实 Probe 不证明五平台实时全链可用。
- 归档导航：不可变实现链接 + 完整附件原始路径，没有独立导航 blocker；原生归档只移动 CHANGE.md。

| ID | 优先级 | 已确认机制 | 修复与目标回归 | 当前状态 |
| --- | --- | --- | --- | --- |
| F-662-001 | P1 | 快手号搜索忽略同时配置的其他稳定身份 | 所有身份共同约束，缺字段拒绝；搜索 ID/eid/主页冲突与一致组合 | Owner 已修复，待 REPAIR_VERIFY |
| F-662-002 | P1 | Discovery 合法但 Detail 作者错配仍持久化 | 在 Canonical/入库/导出前校验作品及作者；四平台正确列表/错误 Detail | Owner 已修复，待 REPAIR_VERIFY |
| F-662-003 | P2 | 过滤坏项后把畸形响应当正常空页 | 四平台保留坏项位置、区分结构缺失；混合坏项与缺失列表 | Owner 已修复，待 REPAIR_VERIFY |
| F-662-004 | P2 | B站数字字符串续页值被当成 opaque token | 数字字符串先转整数；整数、字符串、opaque fallback、缺失和停滞 | Owner 已修复，待 REPAIR_VERIFY |
| F-662-005 | P2 | 手工 main 对账号 partial 打印完成 | 运行/账号/评论终态检查，保留文件和停止原因；main() partial 回归 | Owner 已修复，待 REPAIR_VERIFY |
| F-662-006 | P2 | 根评论输出去重抑制后续回复发现 | 输出与展开状态独立，共享上限且避免重复展开；同根 App 0/1 和 Web 未知/1/2 | Owner 已修复，待 REPAIR_VERIFY |
| F-662-007 | P2 | 小红书 all 已达数量时丢失非正常分页终止 | 独立 subclass 接入严格终态，保留原导出；真实公开入口停滞/正常结束 | Owner 已修复，待 REPAIR_VERIFY |
| F-662-008 | P2 | 未跟踪 .env 被链接成仓库文档 | 本地路径保留代码格式，继续链接真实 .env.example；check_docs | Owner 已修复，待 REPAIR_VERIFY |

## 修复证据的阶段边界

首次新增目标场景运行：20 failed、52 passed；已有不受影响场景保留。
之后修复回归：72 passed。小红书停滞 fixture 已修正为非空重复回复页，正常空页不冒充停滞。
快手未知计数扩展场景已由完整修复后 preflight 覆盖：1931 passed、16 skipped、12 subtests passed；Ruff 39 文件、mypy 435 源文件；check_docs exit 0。旧快手提取测试从过滤坏项改为明确保留坏项，新增公开入口测试同时验证合法作品保留、逐项错误定位及 partial。
本记录不宣称尚未执行的 REPAIR_VERIFY、官方 CI、merge、main-fresh 或 Archive 已完成。
