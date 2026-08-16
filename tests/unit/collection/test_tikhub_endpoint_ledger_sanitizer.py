"""TikHub Endpoint Ledger 去标识化回归测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_probe_module() -> ModuleType:
    path = Path(__file__).resolve().parents[3] / "scripts/dev/probe_tikhub_endpoint_ledger.py"
    name = "_aima_tikhub_endpoint_ledger_probe_test"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 TikHub Endpoint Ledger Probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_response_sanitizer_redacts_long_numeric_token_inside_safe_enum_string() -> None:
    probe = _load_probe_module()
    pseudonyms = probe.Pseudonymizer()

    sanitized = probe.sanitize_response(
        {"type": "video 12345678901"},
        pseudonyms=pseudonyms,
    )

    assert sanitized == {"type": "id-0001"}


def test_response_sanitizer_keeps_normal_safe_enum_and_redacts_time() -> None:
    probe = _load_probe_module()
    pseudonyms = probe.Pseudonymizer()

    sanitized = probe.sanitize_response(
        {
            "type": "video",
            "create_time": "2026-08-16T13:00:00Z",
            "opaque": "12345678901",
        },
        pseudonyms=pseudonyms,
    )

    assert sanitized == {
        "type": "video",
        "create_time": "<redacted-time>",
        "opaque": "id-0001",
    }
