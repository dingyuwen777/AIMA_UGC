"""将启动输入中的飞书凭据拆成 Secret 文件与不含凭据的 Connector 配置。"""

from __future__ import annotations

import json
import ntpath
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import SecretStr

from aima_ugc.platform.identity.connector import build_registry, parse_connector
from aima_ugc.platform.security.secrets import validate_secret_ref

CONNECTORS_FILENAME = "feishu-connectors.json"
_FIELDS = frozenset(
    {
        "code",
        "display_name",
        "app_id",
        "app_secret",
        "app_secret_ref",
        "admin_group_id",
        "user_group_id",
        "redirect_uri",
    }
)
_RESERVED = {CONNECTORS_FILENAME, "tikhub_api_key", "llm_api_key"}


class FeishuConfigInputError(ValueError):
    """启动输入无效；错误只描述位置和规则，不包含输入值。"""


@dataclass(frozen=True, slots=True)
class FeishuConfigInput:
    """保存已校验的公开配置和被遮蔽的凭据。"""

    connectors_json: str | None
    secrets: tuple[tuple[str, SecretStr], ...] = ()


def _filesystem_ref(ref: str) -> str:
    """Windows 先拒绝设备名/尾随点并按大小写等价比较，Linux 保留原有引用语义。"""
    if os.name == "nt":
        if ntpath.isreserved(ref):
            raise ValueError("Windows 不允许该 Secret 文件名")
        return ref.casefold()
    return ref


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """拒绝 JSON 重复字段，避免人工填写值被后项静默覆盖。"""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise FeishuConfigInputError("AIMA_FEISHU_CONNECTORS 包含重复 JSON 字段")
        result[key] = value
    return result


def parse_feishu_config_input(raw: str | None) -> FeishuConfigInput:
    """复用正式 Connector 校验；在进入 Pydantic/业务进程前移除明文凭据。"""
    if raw is None or not raw.strip():
        return FeishuConfigInput(None)
    if len(raw.encode("utf-8")) > 65_536:
        raise FeishuConfigInputError("AIMA_FEISHU_CONNECTORS 超过 64 KiB")
    try:
        items = json.loads(raw, object_pairs_hook=_unique_object)
    except ValueError, TypeError:
        raise FeishuConfigInputError(
            "AIMA_FEISHU_CONNECTORS 必须是合法 JSON，且不能有重复字段"
        ) from None
    if not isinstance(items, list) or not items:
        raise FeishuConfigInputError("AIMA_FEISHU_CONNECTORS 必须是非空 JSON 数组；停用时留空")
    public: list[dict[str, object]] = []
    secrets: list[tuple[str, SecretStr]] = []
    refs: list[str] = []
    for index, item in enumerate(items, start=1):
        try:
            if not isinstance(item, dict) or item.keys() - _FIELDS:
                raise ValueError
            clean = {key: value for key, value in item.items() if key != "app_secret"}
            if "app_secret_ref" not in clean:
                clean["app_secret_ref"] = f"feishu_{clean.get('code', '')}_secret"
            connector = parse_connector(clean, index=index - 1)
            ref = validate_secret_ref(connector.app_secret_ref)
            comparable = _filesystem_ref(ref)
            if comparable.split("/")[0] in _RESERVED:
                raise ValueError
            value = item.get("app_secret")
            if value is not None and value != "":
                if not isinstance(value, str) or not value.strip() or value != value.strip():
                    raise ValueError
                if any(char in value for char in "\r\n\x00"):
                    raise ValueError
                secrets.append((ref, SecretStr(value)))
            clean["app_secret_ref"] = ref
            public.append(clean)
            refs.append(comparable)
        except ValueError, TypeError:
            raise FeishuConfigInputError(
                f"AIMA_FEISHU_CONNECTORS 第 {index} 项无效："
                "检查字段、code、Secret 引用及 app_secret 格式"
            ) from None
    try:
        build_registry([parse_connector(item, index=i) for i, item in enumerate(public)])
        if len(refs) != len(set(refs)):
            raise ValueError
        if any(a != b and b.startswith(a + "/") for a in refs for b in refs):
            raise ValueError
    except ValueError:
        raise FeishuConfigInputError(
            "AIMA_FEISHU_CONNECTORS 存在重复身份/引用、嵌套文件冲突、组冲突或回调地址不匹配"
        ) from None
    return FeishuConfigInput(json.dumps(public, ensure_ascii=False), tuple(secrets))


def _validate_target(path: Path) -> None:
    """拒绝目标及其父级链接，防止初始化写入批准根以外的位置。"""
    for current in (path, *path.parents):
        if current.is_symlink() or current.is_junction():
            raise FeishuConfigInputError("飞书配置目标或父目录不允许链接")
        if current.exists() and current != path and not current.is_dir():
            raise FeishuConfigInputError("飞书配置父路径不是目录")
    if path.exists() and not path.is_file():
        raise FeishuConfigInputError("飞书配置目标不是普通文件")


def _replace_private_file(path: Path, value: str, owner: tuple[int, int] | None) -> None:
    """以原子替换落盘显式启动输入；与 Provider 的不可变 Secret 写入策略分离。"""
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        if owner is not None and sys.platform != "win32":
            os.chown(directory, *owner)
    descriptor, temporary = tempfile.mkstemp(prefix=".feishu-", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value + "\n")
        os.chmod(temporary_path, 0o600)
        if owner is not None and sys.platform != "win32":
            os.chown(temporary_path, *owner)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def materialize_feishu_config(
    root: Path,
    config: FeishuConfigInput,
    *,
    write_manifest: bool = False,
    owner: tuple[int, int] | None = None,
) -> None:
    """先校验全部目标再写入；缺省凭据保留手工文件，显式凭据在重启时更新。"""
    if owner is not None and os.name != "posix":
        raise FeishuConfigInputError("固定 UID/GID 的飞书初始化仅支持 POSIX")
    root = root.absolute()
    writes = [(root / ref, secret.get_secret_value()) for ref, secret in config.secrets]
    if write_manifest:
        writes.append((root / CONNECTORS_FILENAME, config.connectors_json or "null"))
    try:
        for path, _value in writes:
            _validate_target(path)
        for path, value in writes:
            _replace_private_file(path, value, owner)
    except OSError:
        raise FeishuConfigInputError("无法写入飞书运行配置，请检查 Secret 目录及权限") from None
