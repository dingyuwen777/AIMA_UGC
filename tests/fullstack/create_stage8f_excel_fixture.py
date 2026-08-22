"""生成 Stage 8F 浏览器真实导入使用的确定性 Excel fixture。"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("用法: python tests/fullstack/create_stage8f_excel_fixture.py <output.xlsx>")

    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "文章"
    sheet.append(
        [
            "媒体名称（中文）",
            "标题",
            "内文",
            "作者",
            "出版日期",
            "原文链接",
        ]
    )
    sheet.append(
        [
            "小红书",
            "爱玛 Stage8F 浏览器真实导入",
            "公司内网 V1 Full-stack Acceptance 测试内容",
            "Stage8F 测试账号",
            "2026-08-22 12:00:00",
            "https://www.xiaohongshu.com/explore/stage8f-fullstack-content-1",
        ]
    )
    workbook.save(output)
    workbook.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
