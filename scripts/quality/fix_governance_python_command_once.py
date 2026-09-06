"""一次性校准 AIMA 治理检查器对真实 Python 入口的识别。"""

from pathlib import Path

checker = Path("scripts/quality/check_agent_governance.py")
text = checker.read_text(encoding="utf-8")
old = '''        project_check_command = f"python {PROJECT_CHANGE_CHECK.as_posix()}"
        if project_check_command not in gate_text:
            errors.append(f"GOV007 {COMPLETION_OWNER.as_posix()}: 必须执行 AIMA 顶层 Change 门禁")
'''
new = '''        project_check_commands = (
            f"python {PROJECT_CHANGE_CHECK.as_posix()}",
            f"python3 {PROJECT_CHANGE_CHECK.as_posix()}",
        )
        if not any(command in gate_text for command in project_check_commands):
            errors.append(f"GOV007 {COMPLETION_OWNER.as_posix()}: 必须执行 AIMA 顶层 Change 门禁")
'''
if new not in text:
    if old not in text:
        raise SystemExit("governance checker baseline missing")
    checker.write_text(text.replace(old, new, 1), encoding="utf-8")

test_path = Path("tests/unit/test_agent_governance.py")
test_text = test_path.read_text(encoding="utf-8")
marker = '''def test_checker_rejects_workflow_bypassing_project_change_carrier(tmp_path: Path) -> None:
'''
insert = '''def test_checker_accepts_python3_project_change_gate_command(tmp_path: Path) -> None:
    """项目门禁通过系统 python3 执行时仍应被识别为真实接线，而不是 GOV007 缺失。"""
    _minimal_repository(tmp_path)
    workflow_path = tmp_path / ".github/workflows/ci.yml"
    workflow = workflow_path.read_text(encoding="utf-8").replace(
        "python scripts/quality/check_change_completion.py",
        "python3 scripts/quality/check_change_completion.py",
    )
    _write(workflow_path, workflow)
    errors = CHECK_REPOSITORY(tmp_path)
    assert not any(
        error.startswith("GOV007 .github/workflows/ci.yml")
        for error in errors
    )


'''
if "test_checker_accepts_python3_project_change_gate_command" not in test_text:
    if marker not in test_text:
        raise SystemExit("governance test insertion marker missing")
    test_path.write_text(test_text.replace(marker, insert + marker, 1), encoding="utf-8")
