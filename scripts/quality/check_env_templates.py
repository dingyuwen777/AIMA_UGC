"""验证受控 env 模板；不读取用户配置、Secret 或启动任何服务。"""

from __future__ import annotations

import argparse
import re
import runpy
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ("env.local.example", "env.production.example")
KEY = re.compile(r"[A-Z][A-Z0-9_]*\Z")


def parse_template(
    text: str,
    source: str,
    *,
    legacy_duplicates: bool = False,
    preserve_syntax: bool = False,
) -> dict[str, str]:
    """解析声明并拒绝歧义；风险比较保留引号/转义/插值，错误不输出敏感值。"""
    values: dict[str, str] = {}
    assignments = runpy.run_path(str(ROOT / "scripts/dev/local_runtime.py"))["env_assignments"]
    for number, key, value in assignments(text, source):
        if not KEY.fullmatch(key):
            raise ValueError(f"{source}:{number}: 必须使用合法 KEY=value 声明")
        if key in values and not legacy_duplicates:
            raise ValueError(f"{source}:{number}: 重复配置键 {key}")
        if "$(" in value or "`" in value:
            raise ValueError(f"{source}:{number}: {key} 不允许命令替换")
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"{source}:{number}: {key} 引号未闭合")
            if not preserve_syntax:
                quote = value[0]
                value = value[1:-1]
                if quote == "'":
                    value = value.replace("\\'", "'")
        values[key] = value
    return values


def check_templates(root: Path, *, static_only: bool = False, compose: bool = False) -> None:
    """静态阶段兼容 Runner Python；配置阶段复用生产解析与 Release 模板重写。"""
    parsed = {
        name: parse_template((root / name).read_text(encoding="utf-8"), name) for name in TEMPLATES
    }
    compose_text = (root / "compose.yaml").read_text(encoding="utf-8")
    interpolations = set(re.findall(r"\$\{(AIMA_[A-Z0-9_]+)(?::[-?][^}]*)?\}", compose_text))
    for name, values in parsed.items():
        missing = interpolations - values.keys()
        if missing:
            raise ValueError(f"{name}: 缺少 Compose 插值键 {sorted(missing)}")
    if static_only:
        return
    from aima_ugc.bootstrap.feishu_config_input import parse_feishu_config_input
    from aima_ugc.platform.config import load_settings

    runtime = runpy.run_path(str(root / "scripts/dev/local_runtime.py"))
    known = runtime["_KNOWN_LOCAL_KEYS"]
    for name, values in parsed.items():
        unknown = values.keys() - known
        if unknown:
            raise ValueError(f"{name}: 未知模板配置键 {sorted(unknown)}")
        try:
            # 模板与真实启动一样先拆出凭据；此检查只解析，不落盘。
            clean = dict(values)
            config = parse_feishu_config_input(clean.get("AIMA_FEISHU_CONNECTORS"))
            clean["AIMA_FEISHU_CONNECTORS"] = config.connectors_json or ""
            load_settings(clean, base_dir=root)
        except ValueError:
            # Pydantic 的默认错误可能包含输入，模板门禁不回显配置值。
            raise ValueError(
                f"{name}: PlatformSettings 配置校验失败；请检查对应键和身份配置"
            ) from None
    release = runpy.run_path(str(root / "scripts/release/release_bundle.py"))
    with tempfile.TemporaryDirectory(prefix="aima-template-") as directory:
        target = Path(directory) / "env.production.example"
        release["_replace_env_values"](
            root / "env.production.example", target, {"AIMA_IMAGE_TAG": "template-smoke"}
        )
        expected = {**parsed["env.production.example"], "AIMA_IMAGE_TAG": "template-smoke"}
        if parse_template(target.read_text(encoding="utf-8"), target.name) != expected:
            raise ValueError("env.production.example: Release 重写丢失或改变非目标配置")
    if compose:
        for name in TEMPLATES:
            subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    "compose.yaml",
                    "--env-file",
                    name,
                    "config",
                    "--quiet",
                ],
                cwd=root,
                check=True,
                capture_output=True,
            )
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "compose.yaml",
                "-f",
                "compose.windows.yaml",
                "--env-file",
                "env.local.example",
                "config",
                "--quiet",
            ],
            cwd=root,
            check=True,
            capture_output=True,
        )


def main() -> int:
    """只检查 Git 中的两份模板，不打印解析后的值。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static", action="store_true", help="仅执行无项目依赖的静态检查")
    parser.add_argument("--compose", action="store_true", help="验证 Compose 渲染，不启动服务")
    args = parser.parse_args()
    try:
        check_templates(ROOT, static_only=args.static, compose=args.compose)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        reason = "Compose 渲染失败" if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print(f"配置模板检查失败：{reason}")
        return 1
    print("配置模板静态/运行配置与适用消费者检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
