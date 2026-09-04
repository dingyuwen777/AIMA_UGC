"""生成 Stage 12 Real Full-stack 的普通导入与服务器历史迁移 Fixture。"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook

_HEADERS = (
    "媒体名称（中文）",
    "标题",
    "内文",
    "作者",
    "出版日期",
    "原文链接",
)


def _write_xlsx(path: Path, rows: tuple[tuple[str | None, ...], ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("文章")
    sheet.append(_HEADERS)
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    workbook.close()


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(
            "用法: python tests/fullstack/create_stage12_historical_fixture.py "
            "<ordinary.xlsx> <historical-root>"
        )
    ordinary_path = Path(sys.argv[1])
    historical_root = Path(sys.argv[2])
    common = ("小红书", "Stage12 Full-stack 作者", "2025-01-02 10:00:00")
    _write_xlsx(
        ordinary_path.with_name("analysis-streaming.xlsx"),
        tuple(
            (
                "小红书",
                f"爱玛 并发验收 {name}",
                "爱玛通勤舒适性验收",
                "验收用户",
                "2026-09-04 01:00:00",
                f"https://www.xiaohongshu.com/explore/streaming-{name}",
            )
            for name in ("A", "B")
        ),
    )
    _write_xlsx(
        ordinary_path,
        (
            (
                common[0],
                "爱玛 Stage12 当前标题",
                None,
                common[1],
                common[2],
                "https://www.xiaohongshu.com/explore/stage12-fullstack-fill",
            ),
            (
                common[0],
                "爱玛 Stage12 保持不变",
                "相同正文",
                common[1],
                common[2],
                "https://www.xiaohongshu.com/explore/stage12-fullstack-unchanged",
            ),
            (
                common[0],
                "爱玛 Stage12 当前冲突",
                "当前正文",
                common[1],
                common[2],
                "https://www.xiaohongshu.com/explore/stage12-fullstack-conflict",
            ),
        ),
    )
    historical_rows = (
        (
            common[0],
            "爱玛 Stage12 历史冲突标题",
            "历史正文补空成功",
            common[1],
            common[2],
            "https://www.xiaohongshu.com/explore/stage12-fullstack-fill",
        ),
        (
            common[0],
            "爱玛 Stage12 保持不变",
            "相同正文",
            common[1],
            common[2],
            "https://www.xiaohongshu.com/explore/stage12-fullstack-unchanged",
        ),
        (
            common[0],
            "爱玛 Stage12 历史新建",
            "新建正文",
            common[1],
            common[2],
            "https://www.xiaohongshu.com/explore/stage12-fullstack-created",
        ),
        (
            common[0],
            "爱玛 Stage12 历史冲突",
            "当前正文",
            common[1],
            common[2],
            "https://www.xiaohongshu.com/explore/stage12-fullstack-conflict",
        ),
    ) + tuple(
        (
            common[0],
            f"爱玛 Stage12 恢复填充 {index:03d}",
            "用于形成第二个真实 Chunk",
            common[1],
            "2024-01-01 10:00:00",
            f"https://www.xiaohongshu.com/explore/stage12-fullstack-filler-{index:03d}",
        )
        for index in range(97)
    )
    _write_xlsx(
        historical_root / "history.xlsx",
        historical_rows,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
