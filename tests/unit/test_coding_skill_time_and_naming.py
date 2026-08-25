import runpy
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
CODING_ROOT = ROOT / ".agents" / "skills" / "coding"
LEGACY_SKILL_NAME = "reliable" + "-vibe-coding"
LEGACY_ROOT = ROOT / ".agents" / "skills" / LEGACY_SKILL_NAME


def _active_skill_root() -> Path:
    """在迁移 Red 阶段允许读取旧 Skill，以便分别暴露每条缺失规则。"""
    return CODING_ROOT if CODING_ROOT.exists() else LEGACY_ROOT


def _read_skill(relative_path: str) -> str:
    """读取当前可用 Skill 中的 UTF-8 文本文件。"""
    return (_active_skill_root() / relative_path).read_text(encoding="utf-8")


def _current_script_path() -> Path:
    """在迁移前后选择当前真实 CLI 脚本，仅用于建立 Red/Green 回归。"""
    new_path = _active_skill_root() / "scripts" / "coding.py"
    if new_path.exists():
        return new_path
    return _active_skill_root() / "scripts" / "rvc.py"


def test_coding_is_the_only_live_skill_name() -> None:
    """当前 Skill、目录、CLI 和 Agent invocation 必须统一使用 coding。"""
    assert CODING_ROOT.is_dir()
    assert not LEGACY_ROOT.exists()
    assert (CODING_ROOT / "scripts" / "coding.py").is_file()
    assert not (CODING_ROOT / "scripts" / "rvc.py").exists()

    skill = (CODING_ROOT / "SKILL.md").read_text(encoding="utf-8")
    agent = (CODING_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert "name: coding" in skill
    assert "# Coding" in skill
    assert 'display_name: "Coding"' in agent
    assert "Use $coding." in agent
    assert LEGACY_SKILL_NAME not in skill
    assert LEGACY_SKILL_NAME not in agent


def test_project_context_is_fixed_under_agents_and_uses_beijing_time(tmp_path: Path) -> None:
    """项目缓存必须固定写入 .agents，并使用带 +08:00 的北京时间。"""
    namespace = runpy.run_path(str(_current_script_path()))
    context_path = namespace["_context_path"](tmp_path)
    assert context_path == tmp_path / ".agents" / "project-context.json"

    context, mode = namespace["ensure_project_context"](tmp_path, force=True)
    assert mode == "created"
    assert context_path.is_file()

    generated_at = datetime.fromisoformat(context["generated_at"])
    assert generated_at.utcoffset() == timedelta(hours=8)
    assert generated_at.tzinfo is not None
    assert namespace["BEIJING_TIMEZONE"] == ZoneInfo("Asia/Shanghai")


def test_skill_requires_beijing_time_for_all_agent_owned_time() -> None:
    """Skill 必须把北京时间作为所有 Agent 自有时间语义的统一默认。"""
    skill = _read_skill("SKILL.md")
    discovery = _read_skill("references/01_项目发现与可失效缓存.md")
    workflows = _read_skill("references/05_设计实施与根因调试.md")

    for text in (skill, discovery, workflows):
        assert "Asia/Shanghai" in text
        assert "北京时间" in text
    assert "所有时间相关" in skill


def test_skill_requires_canonical_beijing_log_prefix() -> None:
    """日志规则必须固定北京时间、毫秒、源码位置和大写级别前缀。"""
    skill = _read_skill("SKILL.md")
    workflows = _read_skill("references/05_设计实施与根因调试.md")
    canonical = "[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message"

    assert canonical in skill
    assert canonical in workflows
    assert "毫秒固定三位" in workflows
    assert "源文件名和真实调用行号" in workflows
    assert "LEVEL 使用大写" in workflows


def test_aima_live_navigation_uses_coding_skill_paths() -> None:
    """AIMA 当前导航和 Change Gate 不能继续调用旧 Skill 路径。"""
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    gate = (ROOT / ".github" / "workflows" / "change-completion-gate.yml").read_text(
        encoding="utf-8"
    )
    blueprint = (ROOT / "docs" / "blueprint" / "06_开发约束与分阶段实施.md").read_text(
        encoding="utf-8"
    )
    corpus = "\n".join((agents, gate, blueprint))

    assert ".agents/skills/coding/" in corpus
    assert LEGACY_SKILL_NAME not in corpus
    assert "Run Coding completion-gate tests" in gate
    assert "scripts/coding.py" in agents
