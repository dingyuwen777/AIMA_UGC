#!/usr/bin/env python3
"""Correct the temporary finalizer before its second one-shot execution."""

from pathlib import Path

path = Path("scripts/dev/runtime_config_finalize.py")
text = path.read_text(encoding="utf-8")
old = 'readonly = "\\n      read_only: true" if provider_read_only else ""'
new = 'readonly = "\\n        read_only: true" if provider_read_only else ""'
if text.count(old) != 1:
    raise SystemExit("temporary finalizer readonly indentation marker not found exactly once")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
