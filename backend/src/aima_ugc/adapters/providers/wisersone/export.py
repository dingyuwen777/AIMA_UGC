"""复用网站真实任务协议的提交、轮询和下载；人工与 Worker 共用。"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse
from uuid import UUID, uuid4
from zipfile import ZipFile

from playwright.sync_api import BrowserContext, Page, Response, sync_playwright

from . import _browser as web
from .auth import atomic_write, auth_lock, default_auth_root, prepare_auth_locked
from .models import ExportCancelled, ExportProgress, ExportTask, SubmissionUnknown


class WisersOneExporter:
    """每阶段独立恢复会话，锁只覆盖会话刷新，不覆盖网站生成等待。"""

    def __init__(self, *, auth_dir: Path | None = None, headless: bool = True) -> None:
        self.auth_dir = auth_dir or default_auth_root()
        self.headless = headless

    @contextmanager
    def _session(self) -> Iterator[tuple[BrowserContext, Page]]:
        with auth_lock(self.auth_dir):
            paths = prepare_auth_locked(self.auth_dir)
            with sync_playwright() as playwright:
                browser, context, _, _, _ = web._open_context(
                    playwright,
                    self.auth_dir / "browser-profile",
                    paths.state,
                    headless=self.headless,
                )
                authenticated = False
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    page, _, _ = web._ensure_authenticated(
                        context,
                        page,
                        runtime_state_path=paths.runtime,
                        allow_manual=not self.headless,
                    )
                    authenticated = True
                    yield context, page
                finally:
                    try:
                        if authenticated:
                            web._save_storage_state_atomic(context, paths.state)
                    finally:
                        context.close()
                        if browser is not None:
                            browser.close()

    def _task_path(self, run_id: UUID) -> Path:
        return self.auth_dir / f"export-{run_id.hex}.json"

    def saved_task(self, run_id: UUID) -> ExportTask | None:
        """本地提交回执补齐 PG 提交前崩溃窗口；不推断没有回执的未知提交。"""
        path = self._task_path(run_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_bytes())
            task = data["task_id"]
            if data["schema_version"] != "wisersone-export-receipt.v1" or not isinstance(task, str):
                raise ValueError
            if not task:
                raise ValueError
            return ExportTask(task)
        except OSError, ValueError, KeyError, TypeError:
            raise SubmissionUnknown("WisersOne 提交回执损坏，请核对网站下载记录。") from None

    def submit(
        self,
        run_id: UUID,
        *,
        before_submit: Callable[[], None] = lambda: None,
        on_submitted: Callable[[ExportTask], None] = lambda task: None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> ExportTask:
        """提交一次；在点击前记录未知发送意图，在得到 task_id 后立即保存回执。"""
        previous = self.saved_task(run_id)
        if previous is not None:
            return previous
        with self._session() as (_, page):
            web._dismiss_known_page_overlays(page)
            web._select_last_24_hours(page)
            for platform in ("微博", "抖音", "快手", "小红书", "哔哩哔哩"):
                web._safe_click(
                    page.get_by_text(platform, exact=True).filter(visible=True),
                    f"选择平台“{platform}”",
                    timeout=60_000,
                )
            web._select_monitor_folders(page, ("公司品牌", "友商新闻"))
            page.wait_for_timeout(5_000)
            entry = web._find_export_entry_button(page)
            web._safe_click(entry, "打开导出入口")
            web._open_download_field_panel(page)
            web._configure_download_fields(page)
            if cancelled():
                raise ExportCancelled
            before_submit()

            def matches(response: Response) -> bool:
                parsed = urlparse(response.url)
                return (
                    parsed.hostname == web._DATACENTER_HOST
                    and parsed.path == "/ndcApi/v1/download_tasks"
                    and response.request.method == "POST"
                )

            try:
                with page.expect_response(matches, timeout=60_000) as pending:
                    # 此按钮只点击一次；结果未知时不能使用重试点击 helper。
                    page.get_by_role("button", name="下载", exact=True).click(timeout=60_000)
                response = pending.value
                data = response.json()
                task_id = data.get("data", {}).get("task_id")
                if not 200 <= response.status < 300 or not isinstance(task_id, str) or not task_id:
                    raise ValueError
            except Exception:
                raise SubmissionUnknown(
                    "WisersOne 提交结果未知，请核对网站下载记录；未自动重复提交。"
                ) from None
            task = ExportTask(task_id)
            atomic_write(
                self._task_path(run_id),
                json.dumps(
                    {"schema_version": "wisersone-export-receipt.v1", "task_id": task_id}
                ).encode(),
            )
            on_submitted(task)
            web._log("INFO", f"已提交导出任务 {task_id}；生成等待无总时间上限。")
            return task

    @staticmethod
    def _notification_request(page: Page) -> tuple[str, dict[str, str]]:
        def matches(response: Response) -> bool:
            parsed = urlparse(response.url)
            return (
                parsed.hostname == web._DATACENTER_HOST
                and parsed.path == "/ndcApi/v1/download_tasks"
                and response.request.method == "GET"
            )

        with page.expect_response(matches, timeout=60_000) as pending:
            web._safe_click(page.locator("button.sc-6581c3cb-0"), "打开通知中心")
        request = pending.value.request
        headers = {
            key: value
            for key, value in request.all_headers().items()
            if key not in {"cookie", "host", "content-length", "connection", "accept-encoding"}
        }
        return request.url, headers

    def poll(
        self,
        task: ExportTask,
        destination: Path,
        *,
        download: bool = True,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> ExportProgress:
        """一次有界轮询；准备中正常返回，由调用者决定下一次执行时间。"""
        if cancelled():
            raise ExportCancelled
        if destination.exists():
            # 恢复已下载的同一文件，不重新调用网站导出。
            with ZipFile(destination) as package:
                if package.testzip() is not None:
                    raise RuntimeError("已下载 Excel 校验失败，未覆盖冻结输入。")
            return ExportProgress(ready=True, percent=100, file=destination)
        with self._session() as (context, page):
            web._dismiss_known_page_overlays(page)
            list_url, headers = self._notification_request(page)
            record = web._read_download_task(context, list_url, headers, task.task_id)
            if record is None:
                return ExportProgress(ready=False, percent=0)
            status = record.get("status")
            if status == "failed":
                raise RuntimeError("WisersOne 网站导出失败，请检查网站下载记录。")
            if status not in {"preparing", "ready"}:
                raise RuntimeError("WisersOne 网站任务状态格式变化。")
            percent = record.get("percent_completed", 0)
            percent = min(100, max(0, int(percent))) if isinstance(percent, (int, float)) else 0
            if status != "ready" or not download:
                return ExportProgress(ready=status == "ready", percent=percent)
            if cancelled():
                raise ExportCancelled
            parsed = urlparse(list_url)
            params = {
                key: value
                for key, value in parse_qsl(parsed.query)
                if key not in {"offset", "limit"}
            }
            params["user_lvl_control"] = "1"
            file_url = urlunparse(
                parsed._replace(
                    path=f"/ndcApi/v1/download_tasks/file/{quote(task.task_id, safe='')}",
                    query=urlencode(params),
                )
            )
            data = web._download_api_json(context, file_url, headers)
            if data is None:
                return ExportProgress(ready=True, percent=100)
            download_url = data.get("download_url")
            if not isinstance(download_url, str) or urlparse(download_url).scheme != "https":
                raise RuntimeError("WisersOne 未返回有效的 HTTPS 下载地址。")
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                response = context.request.get(download_url, timeout=300_000)
                try:
                    if not 200 <= response.status < 300:
                        raise RuntimeError("WisersOne 文件传输失败。")
                    if cancelled():
                        raise ExportCancelled
                    web._save_xlsx_body(response.body(), destination)
                finally:
                    response.dispose()
            except ExportCancelled:
                raise
            except Exception:
                raise RuntimeError("WisersOne 文件传输失败，请恢复本次任务。") from None
            return ExportProgress(ready=True, percent=100, file=destination)


def download_wisersone_xlsx(
    output_dir: str | Path,
    *,
    auth_dir: Path | None = None,
    headless: bool = True,
    poll_interval: float = 15.0,
) -> Path:
    """人工连续执行相同阶段，Ctrl+C 退出；不设置导出生成总等待上限。"""
    run_id = uuid4()
    exporter = WisersOneExporter(auth_dir=auth_dir, headless=headless)
    task = exporter.submit(run_id)
    destination = Path(output_dir).expanduser().resolve() / f"wisersone_last24h_{run_id.hex}.xlsx"
    while True:
        result = exporter.poll(task, destination)
        if result.file is not None:
            web._log("INFO", f"Excel 已保存：{result.file}")
            return result.file
        web._log("INFO", f"任务 {task.task_id}：生成中，进度 {result.percent}%")
        time.sleep(poll_interval)
