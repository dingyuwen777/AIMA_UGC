"""一次性验证 docs 文件名编号迁移；验证完成后删除本文件。"""

from __future__ import annotations

import difflib
import json
import re
import subprocess
from pathlib import Path

DOC_RENAMES = {
    "docs/代码结构与修改导航.md": "docs/01_代码结构与修改导航.md",
    "docs/环境运行与部署.md": "docs/02_环境运行与部署.md",
    "docs/API接口说明.md": "docs/03_API接口说明.md",
    "docs/测试与调试说明.md": "docs/04_测试与调试说明.md",
    "docs/blueprint/01-总体架构与技术选型.md": "docs/blueprint/01_总体架构与技术选型.md",
    "docs/blueprint/02-采集系统与数据标准化.md": "docs/blueprint/02_采集系统与数据标准化.md",
    "docs/blueprint/03-数据库与文件存储.md": "docs/blueprint/03_数据库与文件存储.md",
    "docs/blueprint/04-后端任务API与前端.md": "docs/blueprint/04_后端任务API与前端.md",
    "docs/blueprint/05-日志安全部署与运维.md": "docs/blueprint/05_日志安全部署与运维.md",
    "docs/blueprint/06-开发约束与分阶段实施.md": "docs/blueprint/06_开发约束与分阶段实施.md",
    "docs/blueprint/07-技术决策与实施门禁.md": "docs/blueprint/07_技术决策与实施门禁.md",
    "docs/blueprint/08-采集策略与平台能力.md": "docs/blueprint/08_采集策略与平台能力.md",
    "docs/appendix/PostgreSQL查询与调试实战.md": "docs/appendix/01_PostgreSQL查询与调试实战.md",
    "docs/appendix/Scheduler调度执行与停机恢复.md": "docs/appendix/02_Scheduler调度执行与停机恢复.md",
    "docs/appendix/TikHub五平台真实响应与字段映射.md": "docs/appendix/03_TikHub五平台真实响应与字段映射.md",
    "docs/appendix/TikHub多接口验证与备用策略.md": "docs/appendix/04_TikHub多接口验证与备用策略.md",
    "docs/appendix/TikHub接口选型与真实验证台账.md": "docs/appendix/05_TikHub接口选型与真实验证台账.md",
    "docs/appendix/Excel统一数据导出与离线调试.md": "docs/appendix/06_Excel统一数据导出与离线调试.md",
    "docs/appendix/AI舆情打标与分析实现.md": "docs/appendix/07_AI舆情打标与分析实现.md",
    "docs/appendix/数据入口与统一入库实现.md": "docs/appendix/08_数据入口与统一入库实现.md",
    "docs/appendix/Stage8F前后端能力矩阵与真实验收.md": "docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md",
    "docs/appendix/Word舆情报告生成与排版实现.md": "docs/appendix/10_Word舆情报告生成与排版实现.md",
    "docs/appendix/生产部署与离线Release方案.md": "docs/appendix/11_生产部署与离线Release方案.md",
    "docs/collection/xiaohongshu.md": "docs/collection/01_xiaohongshu.md",
    "docs/collection/douyin.md": "docs/collection/02_douyin.md",
    "docs/collection/weibo.md": "docs/collection/03_weibo.md",
    "docs/collection/bilibili.md": "docs/collection/04_bilibili.md",
    "docs/collection/kuaishou.md": "docs/collection/05_kuaishou.md",
    "docs/guides/Figma与前端设计开发工作流.md": "docs/guides/01_Figma与前端设计开发工作流.md",
    "docs/guides/AIMA持续开发与内网上线通用提示词.md": "docs/guides/02_AIMA持续开发与内网上线通用提示词.md",
    "docs/guides/Windows Docker Desktop Compose运行.md": "docs/guides/03_Windows Docker Desktop Compose运行.md",
    "docs/roadmap/内网V1上线实施计划.md": "docs/roadmap/01_内网V1上线实施计划.md",
    "docs/roadmap/生产上线实施路线.md": "docs/roadmap/02_生产上线实施路线.md",
}

SAME_PATH_FILES = [
    "AGENTS.md",
    "README.md",
    ".agents/skills/reliable-vibe-coding/tests/test_development_guidance.py",
    ".github/workflows/stage6-xiaohongshu-vertical-slice.yml",
    ".github/workflows/stage7-keyword-packs.yml",
    ".github/workflows/stage7-plan-occurrence-run-snapshot.yml",
    "frontend/README.md",
    "backend/src/aima_ugc/adapters/llm/README.md",
    "backend/src/aima_ugc/adapters/providers/tikhub_test/README.md",
    "backend/src/aima_ugc/modules/analysis/README.md",
    "backend/src/aima_ugc/modules/collection/README.md",
    "backend/src/aima_ugc/modules/content/README.md",
    "backend/src/aima_ugc/modules/ingestion/README.md",
    "backend/src/aima_ugc/modules/reporting/README.md",
    "backend/src/aima_ugc/platform/reporting/README.md",
    "docs/appendix/README.md",
    "docs/blueprint/README.md",
    "docs/collection/README.md",
    "docs/guides/README.md",
    "docs/roadmap/README.md",
    "scripts/dev/frontend.py",
    "tests/fixtures/providers/tikhub/README.md",
    "tests/unit/analysis/test_content_labeling.py",
    "tests/unit/collection/test_stage1_stage7_comprehensive_corrective.py",
]

REPLACEMENTS = {Path(old).name: Path(new).name for old, new in DOC_RENAMES.items()}
SELF = Path("scripts/docs_numbering_validate_temp.py")
TEMP_WORKFLOW = Path(".github/workflows/docs-numbering-check.yml")


def pattern_for(old: str) -> re.Pattern[str]:
    if re.match(r"^\d{2}-", old):
        return re.compile(re.escape(old))
    return re.compile(r"(?<!\d{2}_)" + re.escape(old))


PATTERNS = [(old, pattern_for(old), new) for old, new in REPLACEMENTS.items()]


def transform(text: str) -> str:
    for _, pattern, new in PATTERNS:
        text = pattern.sub(new, text)
    return text.replace("\r\n", "\n")


def base_text(path: str) -> str:
    data = subprocess.check_output(["git", "show", f"origin/main:{path}"])
    return data.decode("utf-8").replace("\r\n", "\n")


def current_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")


def assert_equal(expected: str, actual: str, *, source: str, target: str) -> None:
    if expected == actual:
        return
    diff = "".join(
        difflib.unified_diff(
            expected.splitlines(True),
            actual.splitlines(True),
            fromfile=source,
            tofile=target,
            n=3,
        )
    )
    raise SystemExit(f"{target} 存在超出文件名/路径同步的内容变化:\n{diff[:12000]}")


def check_names() -> None:
    bad = [
        str(path)
        for path in Path("docs").rglob("*.md")
        if path.name != "README.md" and not re.match(r"^\d{2}_", path.name)
    ]
    if bad:
        raise SystemExit("存在未按 NN_ 编号的 docs Markdown:\n" + "\n".join(bad))

    expected_blueprint = {
        "01_总体架构与技术选型.md",
        "02_采集系统与数据标准化.md",
        "03_数据库与文件存储.md",
        "04_后端任务API与前端.md",
        "05_日志安全部署与运维.md",
        "06_开发约束与分阶段实施.md",
        "07_技术决策与实施门禁.md",
        "08_采集策略与平台能力.md",
        "README.md",
    }
    actual = {path.name for path in Path("docs/blueprint").glob("*.md")}
    if actual != expected_blueprint:
        raise SystemExit(f"Blueprint 文件集合不符合仅 '-'→'_' 的要求: {sorted(actual)}")


def check_content_preservation() -> None:
    for old, new in DOC_RENAMES.items():
        assert_equal(transform(base_text(old)), current_text(new), source=old, target=new)
    for path in SAME_PATH_FILES:
        assert_equal(
            transform(base_text(path)),
            current_text(path),
            source=f"origin/main:{path}",
            target=path,
        )


def check_skill() -> None:
    skill = current_text(".agents/skills/reliable-vibe-coding/SKILL.md")
    if skill.count("#### `docs/` 技术文档文件名规范") != 1:
        raise SystemExit("Skill 文档命名规范缺失或重复")
    for required in (
        "两位数字加下划线前缀",
        "`README.md` 永远不加编号",
        "代码/功能开发先后和上游依赖关系排序",
        "核心 Blueprint 固定保持当前 01—08 领域顺序",
    ):
        if required not in skill:
            raise SystemExit(f"Skill 命名规则缺少关键约束: {required}")


def should_skip(path: Path) -> bool:
    return (
        Path("changes/archive") == path
        or Path("changes/archive") in path.parents
        or Path(".git") in path.parents
        or path in {SELF, TEMP_WORKFLOW}
    )


def check_stale_references() -> None:
    stale: list[str] = []
    malformed: list[str] = []
    malformed_pattern = re.compile(r"docs/(?:[^/\s)]+/)?\d{2}-\d{2}_[^\s)`]+\.md")
    for path in Path(".").rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(Path("."))
        if should_skip(rel):
            continue
        data = path.read_bytes()
        if b"\x00" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for old, pattern, _ in PATTERNS:
            if pattern.search(text):
                stale.append(f"{rel}: {old}")
        for match in malformed_pattern.findall(text):
            malformed.append(f"{rel}: {match}")
    if stale:
        raise SystemExit("当前有效文件仍存在旧文档名引用:\n" + "\n".join(stale))
    if malformed:
        raise SystemExit("发现混合旧/新编号路径:\n" + "\n".join(malformed))


def check_context() -> None:
    context = json.loads(Path(".reliable-vibe-coding/project-context.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in context.get("documents", []) if isinstance(item, dict) and "path" in item}
    for new in DOC_RENAMES.values():
        if new not in paths:
            raise SystemExit(f"项目事实源索引缺少新文档路径: {new}")
    for old in DOC_RENAMES:
        if old in paths:
            raise SystemExit(f"项目事实源索引仍包含旧文档路径: {old}")
    if str(TEMP_WORKFLOW) in paths or str(SELF) in paths:
        raise SystemExit("项目事实源索引错误包含一次性校验文件")


def check_markdown_links() -> None:
    link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    broken: list[str] = []
    for source in [Path("README.md"), Path("AGENTS.md"), *Path("docs").rglob("*.md")]:
        text = source.read_text(encoding="utf-8")
        for raw in link_re.findall(text):
            target = raw.strip().split()[0].strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = (source.parent / target).resolve()
            try:
                resolved.relative_to(Path.cwd().resolve())
            except ValueError:
                broken.append(f"{source}: path escapes repo -> {raw}")
                continue
            if not resolved.exists():
                broken.append(f"{source}: missing -> {raw}")
    if broken:
        raise SystemExit("当前 Markdown 存在失效本地链接:\n" + "\n".join(broken))


def main() -> None:
    check_names()
    check_content_preservation()
    check_skill()
    check_stale_references()
    check_context()
    check_markdown_links()
    print("文档编号、正文完整性、当前引用、事实源索引与 Markdown 本地链接检查通过。")


if __name__ == "__main__":
    main()
