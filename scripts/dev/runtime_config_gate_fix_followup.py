#!/usr/bin/env python3
"""Temporary follow-up for the PR #318 one-shot gate fixer."""

from pathlib import Path

path = Path("backend/src/aima_ugc/modules/analysis/tables.py")
text = path.read_text(encoding="utf-8")
old = '''        "(status in ('failed','stale','cancelled') and analysis_result_id is null and error_code is not null)",
'''
new = '''        "(status in ('failed','stale','cancelled') and analysis_result_id is null "
        "and error_code is not null)",
'''
if text.count(old) != 1:
    raise SystemExit("analysis status_fields_consistent long line marker not found exactly once")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
