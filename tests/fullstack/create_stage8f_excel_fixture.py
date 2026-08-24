"""生成 Stage 8F 浏览器真实导入使用的确定性 Excel fixture。"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit(
            "用法: python tests/fullstack/create_stage8f_excel_fixture.py "
            "<output.xlsx> [success|worker-failure|manual-review]"
        )

    output = Path(sys.argv[1])
    scenario = sys.argv[2] if len(sys.argv) == 3 else "success"
    if scenario not in {"success", "worker-failure", "manual-review"}:
        raise SystemExit("scenario 只支持 success、worker-failure 或 manual-review")
    output.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "文章"
    if scenario in {"success", "manual-review"}:
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
        if scenario == "success":
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
        else:
            sheet.append(
                [
                    "小红书",
                    "爱玛 Stage8F 人工相关性复核",
                    "这是一条用于验证 AI irrelevant 人工纳入的真实 Full-stack 前置内容",
                    "Stage8F 人工复核账号",
                    "2026-08-23 12:00:00",
                    "https://www.xiaohongshu.com/explore/stage8f-manual-review-content-1",
                ]
            )
            sheet.append(
                [
                    "小红书",
                    "爱玛 Stage8F 人工排除与撤销",
                    "这是一条用于验证 AI relevant 人工排除后再撤销的真实 Full-stack 前置内容",
                    "Stage8F 双向复核账号",
                    "2026-08-23 13:00:00",
                    "https://www.xiaohongshu.com/explore/stage8f-manual-review-content-2",
                ]
            )
    else:
        # OOXML 结构合法，HTTP 上传应成功创建 Job；但缺少正式 Excel Profile 必填列，
        # 由生产 Worker/Mapper 在后台进入 invalid_import 失败终态。
        sheet.append(["错误表头", "标题"])
        sheet.append(["小红书", "爱玛 Stage8F Worker 失败验收"])

    workbook.save(output)
    workbook.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
