from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts" / "quality" / "check_docs.py"
CHECKER = runpy.run_path(str(CHECKER_PATH))
CHECK_REPOSITORY = CHECKER["check_repository"]


def _write(path: Path, content: str) -> None:
    """写入文档检查测试夹具。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_repository(root: Path) -> None:
    """建立满足固定入口要求的最小项目文档树。"""
    _write(root / "README.md", "# Root\n")
    _write(root / "docs/blueprint/README.md", "# Blueprint\n")
    _write(root / "backend/src/example.py", "def example() -> None:\n    pass\n")
    _write(root / "scripts/check.py", "print('ok')\n")


def test_checker_rejects_unlinked_inline_repository_file(tmp_path: Path) -> None:
    """承担导航职责的真实仓库文件 inline-code 必须可点击。"""
    _minimal_repository(tmp_path)
    _write(
        tmp_path / "docs/guide.md",
        "实现入口是 `backend/src/example.py`。\n",
    )

    errors = CHECK_REPOSITORY(tmp_path)

    assert any(error.startswith("DOC007 docs/guide.md:1") for error in errors)
    assert any("../backend/src/example.py" in error for error in errors)


def test_checker_accepts_linked_repository_file(tmp_path: Path) -> None:
    """已经使用相对 Markdown 链接的仓库文件导航不应误报。"""
    _minimal_repository(tmp_path)
    _write(
        tmp_path / "docs/guide.md",
        "实现入口是 [`backend/src/example.py`](../backend/src/example.py)。\n",
    )

    errors = CHECK_REPOSITORY(tmp_path)

    assert not any(error.startswith("DOC007") for error in errors)


def test_checker_rejects_exact_file_navigation_inside_code_fence(tmp_path: Path) -> None:
    """仅列真实文件的代码块不能承担不可点击的导航职责。"""
    _minimal_repository(tmp_path)
    _write(
        tmp_path / "docs/guide.md",
        "实现入口：\n\n```text\nbackend/src/example.py\nscripts/check.py\n```\n",
    )

    errors = CHECK_REPOSITORY(tmp_path)

    assert any(error.startswith("DOC008 docs/guide.md:4") for error in errors)
    assert any(error.startswith("DOC008 docs/guide.md:5") for error in errors)


def test_checker_rejects_file_description_navigation_fence(tmp_path: Path) -> None:
    """“文件路径→职责”代码块本质是导航，应迁移成可点击 Markdown。"""
    _minimal_repository(tmp_path)
    _write(
        tmp_path / "docs/guide.md",
        "实现导航：\n\n```text\nbackend/src/example.py\n→ 业务实现\n\nscripts/check.py\n→ 静态检查\n```\n",
    )

    errors = CHECK_REPOSITORY(tmp_path)

    assert any(error.startswith("DOC008 docs/guide.md:4") for error in errors)
    assert any(error.startswith("DOC008 docs/guide.md:7") for error in errors)


def test_checker_does_not_treat_commands_as_file_navigation(tmp_path: Path) -> None:
    """包含文件参数的可执行命令仍是命令，不应被机械链接化。"""
    _minimal_repository(tmp_path)
    _write(
        tmp_path / "docs/guide.md",
        "运行：\n\n```bash\npython scripts/check.py\n```\n",
    )

    errors = CHECK_REPOSITORY(tmp_path)

    assert not any(error.startswith("DOC008") for error in errors)


def test_checker_does_not_treat_mixed_code_fence_as_navigation(tmp_path: Path) -> None:
    """配置/流程代码块不能因偶然命中仓库文件而整体判成导航。"""
    _minimal_repository(tmp_path)
    _write(
        tmp_path / "docs/guide.md",
        "配置示例：\n\n```text\nbackend/src/example.py\nmode=production\n```\n",
    )

    errors = CHECK_REPOSITORY(tmp_path)

    assert not any(error.startswith("DOC008") for error in errors)


def test_checker_resolves_unique_short_filename(tmp_path: Path) -> None:
    """唯一文件名也属于可定位的真实仓库文件引用。"""
    _minimal_repository(tmp_path)
    _write(tmp_path / "docs/guide.md", "实现见 `example.py`。\n")

    errors = CHECK_REPOSITORY(tmp_path)

    assert any(error.startswith("DOC007 docs/guide.md:1") for error in errors)


def test_checker_does_not_treat_timezone_identifier_as_file_navigation(tmp_path: Path) -> None:
    """时区等无扩展名字面量不能因仓库存在同名文件而被误判为导航。"""
    _minimal_repository(tmp_path)
    _write(tmp_path / ".agents/tzdata/Asia/Shanghai", "TZif2")
    _write(tmp_path / "docs/guide.md", "业务展示时区固定为 `Asia/Shanghai`。\n")

    errors = CHECK_REPOSITORY(tmp_path)

    assert not any(error.startswith(("DOC007", "DOC008")) for error in errors)
