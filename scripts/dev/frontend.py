"""一个命令准备并启动 AIMA_UGC 前端 Vite 开发服务器。"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from local_runtime import (
    LocalDevError,
    ensure_env_local,
    frontend_dependencies_stale,
    prepare_runtime_directories,
    record_frontend_lock_fingerprint,
    repository_root,
    runtime_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="启动 AIMA_UGC 前端开发服务器")
    parser.add_argument("--validate-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--prepare-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    root = repository_root()
    try:
        env_path, created = ensure_env_local(root)
        if args.validate_only:
            print(f"Frontend launcher valid; local config: {env_path}")
            return 0
        return _run(root=root, env_created=created, prepare_only=args.prepare_only)
    except LocalDevError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


def _run(*, root: Path, env_created: bool, prepare_only: bool) -> int:
    print("AIMA_UGC Local Frontend")
    print("=" * 56)
    if env_created:
        print("[INFO] 已从 env.local.example 自动创建 env.local。")

    node = _required_command("node")
    npm = _required_command("npm")
    _verify_versions(root=root, node=node, npm=npm)

    paths = runtime_paths(root)
    prepare_runtime_directories(paths)
    frontend_dir = root / "frontend"
    if frontend_dependencies_stale(paths, frontend_dir):
        print("[INFO] Frontend dependencies missing or package-lock changed; running npm ci...")
        result = subprocess.run(
            [npm, "ci", "--prefix", "frontend"],
            cwd=root,
            check=False,
        )
        if result.returncode != 0:
            raise LocalDevError("npm ci 失败；请检查 Node/npm 版本、网络和 package-lock.json。")
        record_frontend_lock_fingerprint(paths, frontend_dir)
    else:
        print("[OK] Frontend dependencies are current")

    if prepare_only:
        print("[OK] Frontend preparation completed.")
        return 0

    print("[OK] Starting Vite: http://127.0.0.1:5173/")
    print("本地开发使用 Vite 热更新，不需要先执行 production build。")
    try:
        result = subprocess.run(
            [npm, "--prefix", "frontend", "run", "dev"],
            cwd=root,
            check=False,
        )
    except KeyboardInterrupt:
        return 0
    return result.returncode


def _required_command(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:
        raise LocalDevError(f"未找到 {name}。请先按 docs/环境运行与部署.md 初始化开发环境。")
    return resolved


def _verify_versions(*, root: Path, node: str, npm: str) -> None:
    expected_node = (root / ".node-version").read_text(encoding="utf-8").strip()
    package = json.loads((root / "frontend" / "package.json").read_text(encoding="utf-8"))
    package_manager = str(package.get("packageManager", ""))
    expected_npm = package_manager.removeprefix("npm@")

    actual_node = _command_output([node, "--version"]).removeprefix("v")
    actual_npm = _command_output([npm, "--version"])
    if actual_node != expected_node:
        raise LocalDevError(f"Node 版本不匹配：当前 {actual_node}，仓库要求 {expected_node}。")
    if not expected_npm or actual_npm != expected_npm:
        raise LocalDevError(
            f"npm 版本不匹配：当前 {actual_npm}，仓库要求 {expected_npm or '未知'}。"
        )
    print(f"[OK] Node {actual_node} / npm {actual_npm}")


def _command_output(command: list[str]) -> str:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise LocalDevError(f"命令执行失败：{' '.join(command)}")
    return result.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
