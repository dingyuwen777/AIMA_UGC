"""一次性机械迁移 docs 编号引用；运行后由工作流删除本文件。"""

from __future__ import annotations

import re
from pathlib import Path

REPLACEMENTS = {
    "代码结构与修改导航.md": "01_代码结构与修改导航.md",
    "环境运行与部署.md": "02_环境运行与部署.md",
    "API接口说明.md": "03_API接口说明.md",
    "测试与调试说明.md": "04_测试与调试说明.md",
    "01-总体架构与技术选型.md": "01_总体架构与技术选型.md",
    "02-采集系统与数据标准化.md": "02_采集系统与数据标准化.md",
    "03-数据库与文件存储.md": "03_数据库与文件存储.md",
    "04-后端任务API与前端.md": "04_后端任务API与前端.md",
    "05-日志安全部署与运维.md": "05_日志安全部署与运维.md",
    "06-开发约束与分阶段实施.md": "06_开发约束与分阶段实施.md",
    "07-技术决策与实施门禁.md": "07_技术决策与实施门禁.md",
    "08-采集策略与平台能力.md": "08_采集策略与平台能力.md",
    "PostgreSQL查询与调试实战.md": "01_PostgreSQL查询与调试实战.md",
    "Scheduler调度执行与停机恢复.md": "02_Scheduler调度执行与停机恢复.md",
    "TikHub五平台真实响应与字段映射.md": "03_TikHub五平台真实响应与字段映射.md",
    "TikHub多接口验证与备用策略.md": "04_TikHub多接口验证与备用策略.md",
    "TikHub接口选型与真实验证台账.md": "05_TikHub接口选型与真实验证台账.md",
    "Excel统一数据导出与离线调试.md": "06_Excel统一数据导出与离线调试.md",
    "AI舆情打标与分析实现.md": "07_AI舆情打标与分析实现.md",
    "数据入口与统一入库实现.md": "08_数据入口与统一入库实现.md",
    "Stage8F前后端能力矩阵与真实验收.md": "09_Stage8F前后端能力矩阵与真实验收.md",
    "Word舆情报告生成与排版实现.md": "10_Word舆情报告生成与排版实现.md",
    "生产部署与离线Release方案.md": "11_生产部署与离线Release方案.md",
    "xiaohongshu.md": "01_xiaohongshu.md",
    "douyin.md": "02_douyin.md",
    "weibo.md": "03_weibo.md",
    "bilibili.md": "04_bilibili.md",
    "kuaishou.md": "05_kuaishou.md",
    "Figma与前端设计开发工作流.md": "01_Figma与前端设计开发工作流.md",
    "AIMA持续开发与内网上线通用提示词.md": "02_AIMA持续开发与内网上线通用提示词.md",
    "Windows Docker Desktop Compose运行.md": "03_Windows Docker Desktop Compose运行.md",
    "内网V1上线实施计划.md": "01_内网V1上线实施计划.md",
    "生产上线实施路线.md": "02_生产上线实施路线.md",
}

SKILL_SECTION = """

#### `docs/` 技术文档文件名规范

对仓库 `docs/` 下的 Markdown 技术文档，文件名本身承担稳定的阅读与开发顺序导航，必须遵守：

- 每个 `docs/` 子目录独立编号，不使用跨目录全局连续序号；
- 除 `README.md` 外，技术文档统一使用两位数字加下划线前缀：`01_`、`02_`、`03_`……；`README.md` 永远不加编号；
- 编号按代码/功能开发先后和上游依赖关系排序：基础架构、底层能力和前置事实使用更小编号，依赖它们的后续能力使用更大编号；不要按文件创建时间、字母顺序或个人偏好随意编号；
- `docs/blueprint/` 的核心 Blueprint 固定保持当前 01—08 领域顺序，文件名使用 `01_...md` 至 `08_...md`；普通功能任务不得为了插入新主题静默重排核心 Blueprint；
- 新增技术文档时先确定其职责、所属目录和顺序，再选择编号；确需重命名/重新编号时，同一任务同步当前正式文档、README、AGENTS、代码/配置中的有效路径引用；
- `changes/archive/` 保存历史证据，不因当前文档改名批量改写；`docs/assets/` 等非 Markdown 资源不适用本规则；模块级 `README.md` 继续保持 README 命名。

文件名规范只负责导航和排序，不替代 Blueprint/Appendix/Guide/Roadmap 的职责划分，也不能作为修改文档技术内容的理由。
"""


def is_skipped(path: Path) -> bool:
    return Path("changes/archive") == path or Path("changes/archive") in path.parents or Path(".git") in path.parents


def pattern_for(old: str) -> re.Pattern[str]:
    if re.match(r"^\d{2}-", old):
        return re.compile(re.escape(old))
    return re.compile(r"(?<!\d{2}_)" + re.escape(old))


def rewrite_references() -> None:
    patterns = [(pattern_for(old), new) for old, new in REPLACEMENTS.items()]
    for path in Path(".").rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(Path("."))
        if is_skipped(rel):
            continue
        data = path.read_bytes()
        if b"\x00" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        new_text = text
        for pattern, new in patterns:
            new_text = pattern.sub(new, new_text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8", newline="")


def update_skill() -> None:
    path = Path(".agents/skills/reliable-vibe-coding/SKILL.md")
    text = path.read_text(encoding="utf-8")
    marker = "\n### 10. Completion Audit、两阶段复核和新鲜验证\n"
    if SKILL_SECTION.strip() in text:
        return
    if marker not in text:
        raise SystemExit("未找到 SKILL.md 插入锚点")
    path.write_text(text.replace(marker, SKILL_SECTION + marker, 1), encoding="utf-8", newline="")


def verify() -> None:
    bad = [
        str(path)
        for path in Path("docs").rglob("*.md")
        if path.name != "README.md" and not re.match(r"^\d{2}_", path.name)
    ]
    if bad:
        raise SystemExit("未编号文档:\n" + "\n".join(bad))

    stale: list[str] = []
    patterns = [(old, pattern_for(old)) for old in REPLACEMENTS]
    for path in Path(".").rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(Path("."))
        if is_skipped(rel):
            continue
        data = path.read_bytes()
        if b"\x00" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for old, pattern in patterns:
            if pattern.search(text):
                stale.append(f"{rel}: {old}")
    if stale:
        raise SystemExit("仍存在旧文件名引用:\n" + "\n".join(stale))


def cleanup() -> None:
    for name in (
        ".github/workflows/docs-numbering-migration.yml",
        ".github/workflows/docs-numbering-migration-pr.yml",
        ".docs-numbering-trigger",
        "scripts/docs_numbering_migrate_temp.py",
    ):
        path = Path(name)
        if path.exists():
            path.unlink()


def main() -> None:
    rewrite_references()
    update_skill()
    verify()
    cleanup()


if __name__ == "__main__":
    main()
