"""一次性同步 Stage 2 Review 后的 Artifact 原子发布事实。"""

from pathlib import Path

path = Path("docs/blueprint/07-技术决策与实施门禁.md")
text = path.read_text(encoding="utf-8")
old = "同 key 不静默覆盖，并采用同目录临时文件 + fsync + 原子替换；"
new = "同 key 不静默覆盖，并采用同目录临时文件 + fsync + hard-link 原子 no-overwrite 发布；"
if text.count(old) != 1:
    raise SystemExit(f"expected one Stage 2 Artifact wording, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
