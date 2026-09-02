"""生成 Stage 8F 浏览器真实导入使用的确定性 Excel fixture。"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit(
            "用法: python tests/fullstack/create_stage8f_excel_fixture.py "
            "<output.xlsx> [success|worker-failure|manual-review|admin-product]"
        )

    output = Path(sys.argv[1])
    scenario = sys.argv[2] if len(sys.argv) == 3 else "success"
    if scenario not in {"success", "worker-failure", "manual-review", "admin-product"}:
        raise SystemExit("scenario 只支持 success、worker-failure、manual-review 或 admin-product")
    output.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "文章"
    if scenario in {"success", "manual-review", "admin-product"}:
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
        elif scenario == "manual-review":
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
            sheet.append(
                [
                    "小红书",
                    "爱玛 U2 车型证据全栈导入",
                    "验证车型目录、词包关联、Excel 车型匹配、筛选和详情证据闭环",
                    "U2 全栈测试账号",
                    "2026-09-02 12:00:00",
                    "https://www.xiaohongshu.com/explore/u2-vehicle-fullstack-content-1",
                ]
            )
    else:
        # OOXML 结构合法，因缺少正式 Excel Profile 必填列，统一导入链路
        # 必须在不可变快照/预检阶段进入失败终态，不允许启动业务写入。
        sheet.append(["错误表头", "标题"])
        sheet.append(["小红书", "爱玛 Stage8F Worker 失败验收"])

    workbook.save(output)
    workbook.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
