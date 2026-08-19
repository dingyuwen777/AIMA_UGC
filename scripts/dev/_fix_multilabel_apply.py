from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / "backend/src/aima_ugc/platform/export/excel.py"
text = path.read_text(encoding="utf-8")
replacements = {
    'primary_label = "\n".join': r'primary_label = "\n".join',
    'secondary_label = "\n".join': r'secondary_label = "\n".join',
}
for broken, fixed in replacements.items():
    count = text.count(broken)
    if count != 1:
        raise RuntimeError(f"expected one broken newline literal, got {count}: {broken!r}")
    text = text.replace(broken, fixed, 1)
path.write_text(text, encoding="utf-8")
print("multilabel generated newline literals fixed")
