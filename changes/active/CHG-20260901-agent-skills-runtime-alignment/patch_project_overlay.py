from pathlib import Path

AGENTS = Path("AGENTS.md")
START = "<!-- agent-skills:managed:start -->"
END = "<!-- agent-skills:managed:end -->"
FORBIDDEN = (
    "Runtime Mode",
    "Source Mode",
    "研发治理 MCP",
    "Project Payload",
    "Runtime Skill Projection",
    "canonical Reference",
    ".agents/skills/router/",
)


def replace_once(text: str, old: str, new: str) -> str:
    """只替换一个已确认的项目自有文本片段，防止扩大治理范围。"""
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one replacement target, got {count}: {old}")
    return text.replace(old, new, 1)


def split_managed(text: str) -> tuple[str, str, str]:
    """拆分 installer-owned managed block 与两侧项目自有文本。"""
    if text.count(START) != 1 or text.count(END) != 1:
        raise SystemExit("managed marker is not unique")
    left, rest = text.split(START, 1)
    managed, right = rest.split(END, 1)
    return left, START + managed + END, right


original = AGENTS.read_text(encoding="utf-8")
left, managed_before, right = split_managed(original)
project_text = left + right

project_text = replace_once(
    project_text,
    "当前正式项目文档只维护 AIMA 自己的架构、Contract、Schema、测试、CI、部署和开发导航；通用研发治理规则通过上方项目研发治理入口取得，不在 AIMA 文档树复制 canonical Reference 路径或正文。",
    "当前正式项目文档只维护 AIMA 自己的架构、Contract、Schema、测试、CI、部署和开发导航；不在 AIMA 文档树复制外部通用治理规则或其安装、运行实现说明。",
)
project_text = replace_once(
    project_text,
    "永久 CI 只验证 AIMA 自己可维护的项目治理接线、文档/Secret、Change Ready 和产品质量；通用治理能力自身的源码回归由其 canonical Owner 负责，不复制到业务仓库。",
    "永久 CI 只验证 AIMA 自己可维护的项目治理接线、文档/Secret、Change Ready 和产品质量；外部通用治理能力自身的源码回归不复制到业务仓库。",
)
project_text = replace_once(
    project_text,
    "当前已安装的受管治理运行资产继续由正式安装/升级流程维护。普通 AIMA 业务开发不手工迁移、删除或重写这些受管文件；未来版本升级作为独立治理动作执行。",
    "项目中由安装流程维护的受管文件不作为 AIMA 项目事实源；普通业务开发不直接改写，版本更新通过正式安装/升级流程完成。",
)
project_text = replace_once(
    project_text,
    "按上方“项目研发治理入口”执行当前任务需要的通用研发约束；AIMA 项目规则和当前机器事实始终继续生效，受管运行资产不作为项目自有长期事实源直接维护；",
    "AIMA 项目规则和当前机器事实始终继续生效；通用研发方法不得覆盖或替代项目事实；",
)
project_text = replace_once(
    project_text,
    "[`docs/blueprint/06_开发约束与分阶段实施.md`](docs/blueprint/06_开发约束与分阶段实施.md) + 按上方项目研发治理入口取得当前分层验证规则",
    "[`docs/blueprint/06_开发约束与分阶段实施.md`](docs/blueprint/06_开发约束与分阶段实施.md) + 当前实际测试与 CI 配置",
)

for fragment in FORBIDDEN:
    if fragment in project_text:
        raise SystemExit(f"project overlay still contains generic governance implementation: {fragment}")

new_left_length = len(left)
new_left = project_text[:new_left_length]
new_right = project_text[new_left_length:]
updated = new_left + managed_before + new_right
_, managed_after, _ = split_managed(updated)
if managed_before != managed_after:
    raise SystemExit("managed block changed during project overlay calibration")

AGENTS.write_text(updated, encoding="utf-8")
