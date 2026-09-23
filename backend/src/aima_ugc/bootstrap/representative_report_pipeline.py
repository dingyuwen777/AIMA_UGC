"""代表性筛选、行动建议和报告第 6 节的统一编排。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from openpyxl import load_workbook
from PIL import Image

from aima_ugc.adapters.llm.request_audit import LLMRequestAuditWriter
from aima_ugc.adapters.providers.imports import (
    REAL_USER_VOICE_TYPE,
    LabeledContent,
    read_labeled_content_files,
)
from aima_ugc.bootstrap.representative_selection_publication import (
    create_representative_llm,
)
from aima_ugc.modules.analysis.representative_advice import (
    RepresentativeAdviceInput,
    RepresentativeAdviceService,
)
from aima_ugc.modules.analysis.representative_selection import (
    RepresentativeSelectionRun,
    RepresentativeSelectionService,
    SelectedRepresentative,
    build_candidate_pool,
)
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.reporting import (
    DEFAULT_PRIMARY_LABEL,
    DEFAULT_SECONDARY_LABEL,
    RepresentativeReportRow,
    format_representative_labels,
    normalize_representative_content_url,
)

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright


class _ViewportSize(TypedDict):
    width: int
    height: int


class _ScreenshotClip(TypedDict):
    x: float
    y: float
    width: float
    height: float


DEFAULT_REPRESENTATIVE_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "modules" / "analysis" / "prompts" / "zhengfu_shaixuan.md"
)


@dataclass(frozen=True, slots=True)
class RepresentativeReportPreparation:
    """统一流程给报告生成和两个发布器消费的结果。"""

    selection_run: RepresentativeSelectionRun
    rows: tuple[RepresentativeReportRow, ...]
    warnings: tuple[str, ...] = ()


def prepare_representative_report(
    *,
    input_path: Path,
    output_dir: Path,
    settings: PlatformSettings,
    environment: Mapping[str, str] | None = None,
    prompt_path: Path = DEFAULT_REPRESENTATIVE_PROMPT_PATH,
    max_per_group: int = 10,
    selector_pool_size: int = 50,
    screenshots_dir: Path | None = None,
    capture_screenshots: bool = True,
) -> RepresentativeReportPreparation:
    """一次读取 Excel，完成代表性筛选、建议生成和可选截图。"""

    if max_per_group <= 0 or selector_pool_size <= 0:
        raise ValueError("代表性筛选数量参数必须大于 0")
    source = Path(input_path)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    actual_environment = dict(os.environ if environment is None else environment)
    contents, _ = read_labeled_content_files((source,))
    candidate_pool = build_candidate_pool(
        contents,
        real_user_voice_type=REAL_USER_VOICE_TYPE,
    )

    warnings: list[str] = []
    with LLMRequestAuditWriter(target / "representative_llm_requests.jsonl") as audit_writer:
        llm, raw_llm = create_representative_llm(
            settings,
            audit=audit_writer,
            environment=actual_environment,
        )
        try:
            selection_run = RepresentativeSelectionService(
                prompt_path=Path(prompt_path),
                llm=llm,
                max_per_group=max_per_group,
                selector_pool_size=selector_pool_size,
            ).run(candidate_pool.candidates)
            comment_map = _load_comment_map(source, warnings)
            advice_inputs = tuple(
                _advice_input(item_no=index, selected=selected, comment_map=comment_map)
                for index, selected in enumerate(selection_run.selected, start=1)
            )
            advice_by_index = RepresentativeAdviceService(llm=llm).run(advice_inputs)
        finally:
            raw_llm.close()

    rows = _build_report_rows(
        selection_run,
        advice_by_index=advice_by_index,
        comment_map=comment_map,
        warnings=warnings,
        screenshots_dir=screenshots_dir,
        capture_screenshots=capture_screenshots,
        screenshot_output_dir=target,
    )
    _write_selection_artifacts(target, selection_run, rows, warnings)
    return RepresentativeReportPreparation(
        selection_run=selection_run,
        rows=rows,
        warnings=tuple(warnings),
    )


def _advice_input(
    *,
    item_no: int,
    selected: SelectedRepresentative,
    comment_map: Mapping[tuple[str, str], str],
) -> RepresentativeAdviceInput:
    # 避免把代表性选择模型的内部字段直接暴露给建议模型。
    candidate = selected.candidate
    content: LabeledContent = candidate.content
    decision = selected.decision
    sentiment = decision.sentiment
    if sentiment is None:
        raise ValueError("代表性筛选结果缺少情感")
    return RepresentativeAdviceInput(
        item_no=item_no,
        platform=content.platform,
        sentiment=sentiment,
        primary_label=_representative_label(content.primary_label, DEFAULT_PRIMARY_LABEL),
        secondary_label=_representative_label(content.secondary_label, DEFAULT_SECONDARY_LABEL),
        comment_text=_representative_comment(content, comment_map),
        content_title=content.title,
        content_text=content.text,
    )


def _build_report_rows(
    selection_run: RepresentativeSelectionRun,
    *,
    advice_by_index: Mapping[int, str],
    comment_map: Mapping[tuple[str, str], str],
    warnings: list[str],
    screenshots_dir: Path | None,
    capture_screenshots: bool,
    screenshot_output_dir: Path,
) -> tuple[RepresentativeReportRow, ...]:
    screenshot_session = (
        _OptionalScreenshotSession(warnings, target_dir=screenshot_output_dir)
        if capture_screenshots
        else None
    )
    if screenshot_session is None:
        rows = [
            _row_without_screenshot(
                index=index,
                selected=selected,
                advice_by_index=advice_by_index,
                comment_map=comment_map,
            )
            for index, selected in enumerate(selection_run.selected, start=1)
        ]
        return tuple(rows)

    with screenshot_session as session:
        rows = []
        for index, selected in enumerate(selection_run.selected, start=1):
            row = _row_without_screenshot(
                index=index,
                selected=selected,
                advice_by_index=advice_by_index,
                comment_map=comment_map,
            )
            screenshot = _find_local_screenshot(
                row,
                screenshots_dir=screenshots_dir,
            )
            if screenshot is None and session is not None:
                screenshot = session.fetch(row)
            rows.append(
                RepresentativeReportRow(
                    platform=row.platform,
                    sentiment=row.sentiment,
                    content_id=row.content_id,
                    content_url=row.content_url,
                    link_text=row.link_text,
                    comment_text=row.comment_text,
                    primary_label=row.primary_label,
                    secondary_label=row.secondary_label,
                    action_advice=row.action_advice,
                    screenshot_path=screenshot,
                    processing_progress="",
                )
            )
    return tuple(rows)


def _row_without_screenshot(
    *,
    index: int,
    selected: SelectedRepresentative,
    advice_by_index: Mapping[int, str],
    comment_map: Mapping[tuple[str, str], str],
) -> RepresentativeReportRow:
    candidate = selected.candidate
    content: LabeledContent = candidate.content
    decision = selected.decision
    sentiment = decision.sentiment
    if sentiment is None:
        raise ValueError("代表性筛选结果缺少情感")
    return RepresentativeReportRow(
        platform=content.platform,
        sentiment=sentiment,
        content_id=content.content_id,
        content_url=normalize_representative_content_url(
            content.platform,
            content.content_url,
        ),
        link_text=content.title.strip() or content.text.strip() or content.content_url.strip(),
        comment_text=_representative_comment(content, comment_map),
        primary_label=_representative_label(content.primary_label, DEFAULT_PRIMARY_LABEL),
        secondary_label=_representative_label(content.secondary_label, DEFAULT_SECONDARY_LABEL),
        action_advice=advice_by_index.get(index, ""),
        processing_progress="",
    )


def _representative_label(value: str, fallback: str) -> str:
    """返回去重后的标签；输入缺失时使用 Taxonomy 的合法兜底值。"""

    return format_representative_labels(value) or fallback


def _load_comment_map(
    input_path: Path,
    warnings: list[str],
) -> dict[tuple[str, str], str]:
    """按平台 + 内容 ID 关联评论；同一内容取评论点赞最高者。"""

    workbook = load_workbook(input_path, read_only=True, data_only=True)
    try:
        if "评论" not in workbook.sheetnames:
            warnings.append("Excel 缺少评论 Sheet，代表性评论内容列按要求留空")
            return {}
        worksheet = workbook["评论"]
        rows = worksheet.iter_rows(values_only=True)
        try:
            raw_headers = next(rows)
        except StopIteration:
            warnings.append("评论 Sheet 为空，代表性评论内容列按要求留空")
            return {}
        headers = {str(value).strip(): index for index, value in enumerate(raw_headers) if value}
        required = {"平台", "内容ID", "评论内容"}
        if not required.issubset(headers):
            warnings.append("评论 Sheet 缺少平台、内容ID或评论内容字段，代表性评论内容列按要求留空")
            return {}
        likes_index = headers.get("评论点赞")
        result: dict[tuple[str, str], tuple[int, int, str]] = {}
        for row_number, values in enumerate(rows, start=2):
            platform = _platform_text(_cell_text(values, headers["平台"]))
            content_id = _cell_text(values, headers["内容ID"])
            text = _cell_text(values, headers["评论内容"])
            if not platform or not content_id or not text:
                continue
            likes = _integer_or_zero(values, likes_index)
            key = (platform, content_id)
            candidate = (likes, -row_number, text)
            previous = result.get(key)
            if previous is None or candidate[:2] > previous[:2]:
                result[key] = candidate
        return {key: value[2] for key, value in result.items()}
    finally:
        workbook.close()


def _representative_comment(
    content: LabeledContent,
    comment_map: Mapping[tuple[str, str], str],
) -> str:
    """代表性内容没有评论来源时，报告的评论内容列保持空白。"""

    del content, comment_map
    return ""


def _find_local_screenshot(
    row: RepresentativeReportRow,
    *,
    screenshots_dir: Path | None,
) -> Path | None:
    if screenshots_dir is None:
        return None
    root = Path(screenshots_dir)
    safe_id = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in row.content_id
    )
    for candidate in (
        root / f"{row.platform}_{safe_id}.png",
        root / f"{safe_id}.png",
    ):
        if candidate.is_file() and _is_usable_screenshot(candidate):
            return candidate
    return None


class _OptionalScreenshotSession:
    """尽力按抖音桌面端页面样式截图；不可用时安全降级为空。"""

    _DOUYIN_PLATFORM = "抖音"
    _VIEWPORT: _ViewportSize = {"width": 1440, "height": 810}
    # 抖音公开页的登录遮罩不是首屏同步渲染，通常在 5～7 秒后才出现。
    # 先等待动态首屏，再用下面的有界轮询确认媒体已完成绘制，避免把二维码弹窗、
    # 加载中骨架屏或视频黑帧截进报告。
    _PAGE_RENDER_WAIT_MS = 7_000
    _PAGE_READY_TIMEOUT_MS = 20_000
    _PAGE_READY_POLL_MS = 800
    _PAGE_READY_STABLE_POLLS = 2
    _AFTER_DISMISS_WAIT_MS = 800
    # 去掉抖音网页左侧导航和顶部账号区；保留帖子主体、右侧作者、评论和推荐区。
    _POST_CLIP: _ScreenshotClip = {"x": 160, "y": 55, "width": 1280, "height": 755}
    _PROFILE_COPY_IGNORED = shutil.ignore_patterns(
        "Cache",
        "Code Cache",
        "GPUCache",
        "Media Cache",
        "ShaderCache",
        "GrShaderCache",
        "DawnCache",
        "CacheStorage",
        "Singleton*",
    )

    def __init__(self, warnings: list[str], *, target_dir: Path) -> None:
        self._warnings = warnings
        self._target_dir = Path(target_dir)
        self._playwright: Playwright | None = None
        self._browser: Browser | BrowserContext | None = None
        self._page: Page | None = None
        self._browser_executable: Path | None = None
        self._browser_profile: tempfile.TemporaryDirectory[str] | None = None
        self._browser_user_data_dir: Path | None = None
        self._browser_profile_directory: str | None = None
        self._authenticated_fallback_attempted = False

    def __enter__(self) -> _OptionalScreenshotSession | None:
        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            executable = _find_headless_browser()
            if executable is not None:
                self._browser = self._playwright.chromium.launch(
                    executable_path=str(executable),
                    headless=True,
                )
            else:
                self._browser = self._playwright.chromium.launch(headless=True)
            self._page = self._browser.new_page(
                viewport=self._VIEWPORT,
                device_scale_factor=1,
            )
            return self
        except Exception as exc:
            self._close()
            executable = _find_headless_browser()
            if executable is None:
                self._warnings.append(
                    f"公开抖音截图浏览器不可用（{type(exc).__name__}），报告中的截图单元格已留空"
                )
                return None
            self._browser_executable = executable
            self._browser_profile = tempfile.TemporaryDirectory(prefix="aima-douyin-screenshot-")
            self._browser_user_data_dir = Path(self._browser_profile.name)
            self._warnings.append(
                f"无法复用 Edge 登录配置，已使用临时系统浏览器截图：{executable.name}"
            )
            return self

    def __exit__(self, *_: object) -> None:
        self._close()

    def fetch(self, row: RepresentativeReportRow) -> Path | None:
        if (
            (self._page is None and self._browser_executable is None)
            or row.platform != self._DOUYIN_PLATFORM
            or not row.content_url.strip()
        ):
            return None
        target_dir = self._target_dir / "screenshots"
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_id = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in row.content_id
        )
        target = target_dir / f"{row.platform}_{safe_id}.png"
        try:
            target.unlink(missing_ok=True)
            if self._page is not None:
                state = self._prepare_douyin_page(self._page, row.content_url)
                if state is not None and not bool(state.get("ready")):
                    can_use_authenticated = bool(state.get("blocking_login")) and (
                        self._switch_to_authenticated_browser()
                    )
                    if can_use_authenticated:
                        state = self._prepare_douyin_page(self._page, row.content_url)
                    if state is not None and not bool(state.get("ready")):
                        reason = (
                            "仍被登录遮罩拦截"
                            if bool(state.get("blocking_login"))
                            else "页面加载未完成"
                        )
                        self._warnings.append(f"抖音{reason}，已跳过截图：{row.content_id}")
                        return None
                elif _page_requires_login(self._page):
                    if not self._switch_to_authenticated_browser():
                        self._warnings.append(
                            f"抖音页面需要登录且无法启用登录态，已跳过截图：{row.content_id}"
                        )
                        return None
                    self._prepare_douyin_page(self._page, row.content_url)
                    if _page_requires_login(self._page):
                        self._warnings.append(f"抖音页面仍需要登录，已跳过截图：{row.content_id}")
                        return None
                # 登录提示可能在最后一次状态检查之后才被站点重新挂载；截图前再清理
                # 一次，并在真实浏览器上重新确认页面状态。
                if _dismiss_douyin_login_overlay(self._page):
                    self._page.wait_for_timeout(self._AFTER_DISMISS_WAIT_MS)
                final_state = _inspect_douyin_page(self._page)
                if final_state is not None and not bool(final_state.get("ready")):
                    self._warnings.append(f"抖音截图前页面状态不稳定，已跳过：{row.content_id}")
                    return None
                if final_state is None and _page_requires_login(self._page):
                    self._warnings.append(f"抖音页面仍需要登录，已跳过截图：{row.content_id}")
                    return None
                self._page.screenshot(
                    path=str(target),
                    full_page=False,
                    clip=self._POST_CLIP,
                )
            else:
                if not self._capture_with_system_browser(row.content_url, target):
                    self._warnings.append(
                        f"抖音页面需要登录或无法确认登录态，已跳过截图：{row.content_id}"
                    )
                    target.unlink(missing_ok=True)
                    return None
            if target.is_file() and _is_usable_screenshot(target):
                return target
            if target.is_file():
                target.unlink(missing_ok=True)
                self._warnings.append(f"抖音截图疑似仍在加载或画面过暗，已跳过：{row.content_id}")
                return None
            self._warnings.append(f"抖音截图未生成，已跳过：{row.content_id}")
            return None
        except Exception as exc:
            target.unlink(missing_ok=True)
            self._warnings.append(f"抖音截图失败，已跳过：{row.content_id}（{type(exc).__name__}）")
            return None

    def _prepare_douyin_page(
        self,
        page: object,
        url: str,
    ) -> Mapping[str, object] | None:
        goto = getattr(page, "goto", None)
        wait_for_timeout = getattr(page, "wait_for_timeout", None)
        evaluate = getattr(page, "evaluate", None)
        if not callable(goto) or not callable(wait_for_timeout) or not callable(evaluate):
            raise TypeError("Playwright 页面对象缺少截图所需方法")
        goto(url, wait_until="domcontentloaded", timeout=30_000)
        # 抖音正文、评论区和右侧互动栏都是动态渲染，且登录遮罩会延迟弹出。
        wait_for_timeout(self._PAGE_RENDER_WAIT_MS)
        evaluate("window.scrollTo(0, 0)")
        stable_polls = 0
        state: Mapping[str, object] | None = None
        poll_count = max(1, self._PAGE_READY_TIMEOUT_MS // self._PAGE_READY_POLL_MS)
        for _ in range(poll_count + 1):
            dismissed = _dismiss_douyin_login_overlay(page)
            if dismissed:
                # 关闭“登录后免费畅享高清视频”遮罩后，等待帖子主体恢复绘制。
                wait_for_timeout(self._AFTER_DISMISS_WAIT_MS)
            state = _inspect_douyin_page(page)
            if state is None:
                # 测试替身或不兼容的页面对象没有状态诊断能力时，保留旧的降级路径。
                break
            if bool(state.get("ready")):
                stable_polls += 1
                if stable_polls >= self._PAGE_READY_STABLE_POLLS:
                    break
            else:
                stable_polls = 0
            wait_for_timeout(self._PAGE_READY_POLL_MS)
        evaluate("window.scrollTo(0, 0)")
        # 最后一次清理覆盖延迟出现的登录弹窗，并返回清理后的状态给 fetch 判断。
        if _dismiss_douyin_login_overlay(page):
            wait_for_timeout(self._AFTER_DISMISS_WAIT_MS)
            state = _inspect_douyin_page(page)
        return state

    def _switch_to_authenticated_browser(self) -> bool:
        """公开页面被拦截时，按需切换到 Edge 登录态副本。"""

        if self._authenticated_fallback_attempted:
            return False
        self._authenticated_fallback_attempted = True
        authenticated_browser = _find_authenticated_edge_profile()
        if authenticated_browser is None:
            return False
        executable, user_data_dir, profile_directory = authenticated_browser
        try:
            self._close_browser_runtime()
            self._browser_profile = tempfile.TemporaryDirectory(prefix="aima-edge-profile-copy-")
            copied_root = Path(self._browser_profile.name)
            _copy_edge_profile(
                source_root=user_data_dir,
                profile_directory=profile_directory,
                destination_root=copied_root,
                # 类属性中的函数通过实例访问会被绑定成方法，导致
                # shutil.copytree 调用时多出一个 self 参数并抛 TypeError。
                ignore=type(self)._PROFILE_COPY_IGNORED,
            )
            self._browser_executable = executable
            self._browser_profile_directory = profile_directory
            self._browser_user_data_dir = copied_root
            self._start_playwright_browser(executable)
        except Exception as exc:
            self._close()
            reason = (
                "配置文件被 Edge 占用"
                if isinstance(exc, PermissionError)
                else f"登录态副本不可用（{type(exc).__name__}）"
            )
            self._warnings.append(f"{reason}，该条截图留空")
            return False
        self._warnings.append(
            f"公开页面需要登录，已切换到 Edge 登录态副本：{profile_directory}；"
            "已移除左侧导航和顶部账号区"
        )
        return True

    def _start_playwright_browser(self, executable: Path) -> None:
        from playwright.sync_api import sync_playwright

        if self._browser_user_data_dir is None:
            raise RuntimeError("Edge 登录配置副本目录未初始化")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch_persistent_context(
            str(self._browser_user_data_dir),
            headless=True,
            executable_path=str(executable),
            viewport=self._VIEWPORT,
            device_scale_factor=1,
            args=[
                f"--profile-directory={self._browser_profile_directory or 'Default'}",
            ],
        )
        self._page = self._browser.new_page()

    def _capture_with_system_browser(self, url: str, target: Path) -> bool:
        if self._browser_executable is None or self._browser_user_data_dir is None:
            return False
        width = self._VIEWPORT["width"]
        height = self._VIEWPORT["height"]
        command_prefix = [
            str(self._browser_executable),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={width},{height}",
            "--run-all-compositor-stages-before-draw",
            # 系统浏览器兜底不能注入关闭按钮脚本，尽量在延迟遮罩出现前完成截图。
            "--virtual-time-budget=15000",
            f"--user-data-dir={self._browser_user_data_dir}",
        ]
        if self._browser_profile_directory is not None:
            command_prefix.append(f"--profile-directory={self._browser_profile_directory}")
        dom_result = subprocess.run(
            [*command_prefix, "--dump-dom", url],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if dom_result.returncode != 0 or not dom_result.stdout:
            return False
        # 系统浏览器兜底无法注入 DOM 清理脚本；发现大登录弹窗时宁可留空，
        # 也不把登录页写入报告。
        if "登录后免费畅享高清视频" in dom_result.stdout:
            return False
        subprocess.run(
            [*command_prefix, f"--screenshot={target}", url],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        _crop_screenshot_to_post_area(target, clip=self._POST_CLIP)
        return target.is_file() and _is_usable_screenshot(target)

    def _close(self) -> None:
        self._close_browser_runtime()
        if self._browser_profile is not None:
            self._browser_profile.cleanup()
        self._browser_profile = None
        self._browser_user_data_dir = None
        self._browser_profile_directory = None

    def _close_browser_runtime(self) -> None:
        page = self._page
        browser = self._browser
        playwright = self._playwright
        self._page = None
        self._browser = None
        self._playwright = None
        self._browser_executable = None
        for runtime, method_name in (
            (page, "close"),
            (browser, "close"),
            (playwright, "stop"),
        ):
            close = getattr(runtime, method_name, None)
            if callable(close):
                close()


def _find_authenticated_edge_profile() -> tuple[Path, Path, str] | None:
    executable = _find_edge_executable()
    if executable is None:
        return None
    configured_root = os.environ.get("AIMA_EDGE_USER_DATA_DIR", "").strip()
    user_data_dir = (
        Path(configured_root)
        if configured_root
        else Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data"
    )
    if not user_data_dir.is_dir():
        return None
    return executable, user_data_dir, _read_edge_profile_directory(user_data_dir)


def _copy_edge_profile(
    *,
    source_root: Path,
    profile_directory: str,
    destination_root: Path,
    ignore: object,
) -> None:
    """复制登录态所需的 Edge 配置，避免与用户正在运行的 Edge 争抢锁文件。"""

    source_profile = source_root / profile_directory
    if not source_profile.is_dir():
        raise FileNotFoundError(source_profile)
    destination_root.mkdir(parents=True, exist_ok=True)
    local_state = source_root / "Local State"
    if local_state.is_file():
        shutil.copy2(local_state, destination_root / "Local State")
    shutil.copytree(
        source_profile,
        destination_root / profile_directory,
        dirs_exist_ok=True,
        ignore=ignore,  # type: ignore[arg-type]
    )


def _page_requires_login(page: object) -> bool:
    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return False
    try:
        result = evaluate(
            """
            (() => {
              const marker = /登录后(?:免费|查看|查看更多)|扫码登录|验证登录/i;
              const path = (window.location && window.location.pathname) || "";
              if (/\\/(?:passport|login)(?:\\/|$)/i.test(path)) return true;
              const visible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                // 右侧评论面板也会显示“登录后查看更多评论”，但它不是整页登录拦截。
                // 只把抖音居中的大登录弹窗识别为阻断状态。
                return rect.width >= 500 && rect.height >= 280 &&
                  style.display !== "none" && style.visibility !== "hidden" &&
                  Number(style.opacity || "1") > 0;
              };
              const candidates = Array.from(document.querySelectorAll(
                '[role="dialog"], [aria-modal="true"], [class*="douyin_login"], ' +
                '[class*="DouyinLogin"], [class*="login_modal"], [class*="LoginModal"], ' +
                '[class*="passport"], [class*="Passport"]'
              ));
              if (candidates.some((element) => {
                const text = String(element.innerText || element.textContent || "");
                return visible(element) && marker.test(text);
              })) {
                return true;
              }
              return false;
            })()
            """
        )
        return result is True
    except Exception:
        # 仅用于单元测试替身或浏览器兼容性降级；真实浏览器通常会返回 bool。
        return False


def _dismiss_douyin_login_overlay(page: object) -> bool:
    """关闭抖音公开页面的登录提示遮罩，不触发登录或提交任何信息。"""

    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return False
    try:
        result = evaluate(
            """
            (() => {
              const marker = /登录后(?:免费|查看|查看更多)|扫码登录|验证登录/i;
              const visible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return rect.width > 200 && rect.height > 120 &&
                  style.display !== "none" && style.visibility !== "hidden" &&
                  Number(style.opacity || "1") > 0;
              };
              const roots = Array.from(document.querySelectorAll(
                '[role="dialog"], [aria-modal="true"], [class*="douyin_login"], ' +
                '[class*="DouyinLogin"], [class*="login_modal"], [class*="LoginModal"]'
              )).filter((element) => {
                const text = String(element.innerText || element.textContent || "");
                return visible(element) && marker.test(text);
              }).sort((left, right) => {
                const a = left.getBoundingClientRect();
                const b = right.getBoundingClientRect();
                return (b.width * b.height) - (a.width * a.height);
              });
              let dismissed = false;
              for (const root of roots) {
                if (!root.isConnected) continue;
                const rootRect = root.getBoundingClientRect();
                const candidates = [
                  ...Array.from(root.querySelectorAll(
                    'button, [role="button"], [aria-label*="关闭"], ' +
                    '[title*="关闭"], [class*="close"], [class*="Close"]'
                  )),
                  ...Array.from(root.querySelectorAll("svg"))
                    .map((icon) => icon.parentElement)
                    .filter(Boolean),
                ];
                const closeButton = candidates.find((element) => {
                  if (!(element instanceof HTMLElement)) return false;
                  const rect = element.getBoundingClientRect();
                  return rect.width >= 16 && rect.height >= 16 &&
                    rect.x > rootRect.x + rootRect.width * 0.70 &&
                    rect.y < rootRect.y + 120;
                });
                if (closeButton instanceof HTMLElement) {
                  closeButton.click();
                }
                // 只移除已确认是登录提示的节点及其全屏遮罩父节点，避免二维码、
                // 黑色遮罩进入截图；右侧推荐/评论容器本身不会被移除。
                let ancestor = root.parentElement;
                let removedAncestor = false;
                while (ancestor && ancestor !== document.body) {
                  const rect = ancestor.getBoundingClientRect();
                  const style = window.getComputedStyle(ancestor);
                  if (rect.width >= window.innerWidth * 0.9 &&
                      rect.height >= window.innerHeight * 0.9 &&
                      (style.position === "fixed" || style.position === "absolute")) {
                    ancestor.remove();
                    removedAncestor = true;
                    break;
                  }
                  ancestor = ancestor.parentElement;
                }
                if (!removedAncestor && root.isConnected) root.remove();
                dismissed = true;
              }
              return dismissed;
            })()
            """
        )
        return result is True
    except Exception:
        return False


def _inspect_douyin_page(page: object) -> Mapping[str, object] | None:
    """读取抖音公开页的就绪状态，不读取页面账号、Cookie 或用户资料。"""

    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return None
    try:
        result = evaluate(
            """
            (() => {
              const rectOf = (element) => element.getBoundingClientRect();
              const visible = (element) => {
                const rect = rectOf(element);
                const style = window.getComputedStyle(element);
                return rect.width > 0 && rect.height > 0 &&
                  style.display !== "none" && style.visibility !== "hidden" &&
                  Number(style.opacity || "1") > 0;
              };
              const visibleLargeLogin = Array.from(document.querySelectorAll(
                '[role="dialog"], [aria-modal="true"], [class*="douyin_login"], ' +
                '[class*="DouyinLogin"], [class*="login_modal"], [class*="LoginModal"], ' +
                '[class*="passport"], [class*="Passport"]'
              )).some((element) => {
                const rect = rectOf(element);
                const text = String(element.innerText || element.textContent || "");
                return rect.width >= 500 && rect.height >= 280 && visible(element) &&
                  /登录后(?:免费|查看|查看更多)|扫码登录|验证登录/i.test(text);
              });
              const loading = Array.from(document.querySelectorAll(
                '[aria-busy="true"], [class*="loading"], [class*="Loading"], ' +
                '[class*="spinner"], [class*="Spinner"]'
              )).some((element) => {
                if (!visible(element)) return false;
                const rect = rectOf(element);
                if (rect.width >= window.innerWidth * 0.95 &&
                    rect.height >= window.innerHeight * 0.95) return false;
                const text = String(element.innerText || element.textContent || "");
                const className = String(element.className || "");
                return element.getAttribute("aria-busy") === "true" ||
                  /加载中|正在加载|loading|spinner/i.test(`${className} ${text}`);
              });
              const videos = Array.from(document.querySelectorAll("video")).filter((element) => {
                const rect = rectOf(element);
                return visible(element) && rect.width >= 200 && rect.height >= 150;
              });
              const readyVideos = videos.filter((element) =>
                element.readyState >= 2 && element.videoWidth > 0 && element.videoHeight > 0
              );
              const images = Array.from(document.images).filter((element) => {
                const rect = rectOf(element);
                return visible(element) && rect.width >= 80 && rect.height >= 80;
              });
              const readyImages = images.filter((element) =>
                element.complete && element.naturalWidth > 0 && element.naturalHeight > 0
              );
              const canvases = Array.from(document.querySelectorAll("canvas")).filter((element) => {
                const rect = rectOf(element);
                return visible(element) && rect.width >= 200 && rect.height >= 150;
              });
              const mediaPresent = videos.length > 0 || images.length > 0 || canvases.length > 0;
              const mediaReady = videos.length > 0
                ? readyVideos.length > 0
                : images.length > 0
                  ? readyImages.length > 0
                  : canvases.length > 0;
              const bodyText = String(document.body?.innerText || "").trim();
              const bodyReady = bodyText.length >= 80 || readyVideos.length > 0 ||
                readyImages.length >= 2;
              const ready = !visibleLargeLogin && !loading && mediaPresent &&
                mediaReady && bodyReady;
              return {
                ready,
                blocking_login: visibleLargeLogin,
                loading,
                media_present: mediaPresent,
                media_ready: mediaReady,
                body_ready: bodyReady,
                video_count: videos.length,
                ready_video_count: readyVideos.length,
                ready_image_count: readyImages.length,
              };
            })()
            """
        )
        if isinstance(result, Mapping):
            return result
    except Exception:
        return None
    return None


def _is_usable_screenshot(path: Path) -> bool:
    """拒绝损坏、尺寸异常和明显的黑屏/加载占位图。"""

    try:
        with Image.open(path) as image:
            if image.width < 300 or image.height < 200:
                return False
            sample = image.convert("L").resize((64, 64))
            pixels = list(sample.tobytes())
    except (OSError, ValueError):
        return False
    if not pixels:
        return False
    mean = sum(pixels) / len(pixels)
    variance = sum((pixel - mean) ** 2 for pixel in pixels) / len(pixels)
    # 正常截图右侧文字、头像或推荐缩略图会带来足够的非黑像素；保留深色视频，
    # 只拒绝几乎整张都是黑色且没有有效内容的加载帧。
    return not (mean < 35 and variance < 250)


def _find_edge_executable() -> Path | None:
    candidates: list[Path] = []
    for command_name in ("msedge.exe", "msedge"):
        executable = shutil.which(command_name)
        if executable:
            candidates.append(Path(executable))
    for variable_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(variable_name, "").strip()
        if base:
            candidates.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    return _first_existing_path(candidates)


def _read_edge_profile_directory(user_data_dir: Path) -> str:
    """从 Edge 的 Local State 选择最近使用的登录 profile。"""

    try:
        payload = json.loads((user_data_dir / "Local State").read_text(encoding="utf-8"))
        profile = payload.get("profile", {})
        candidates = [
            *profile.get("last_active_profiles", []),
            "Default",
            *profile.get("info_cache", {}).keys(),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and (user_data_dir / candidate).is_dir():
                return candidate
    except (OSError, TypeError, ValueError):
        pass
    return "Default"


def _crop_screenshot_to_post_area(path: Path, *, clip: _ScreenshotClip) -> None:
    if not path.is_file():
        return
    with Image.open(path) as image:
        scale_x = image.width / 1440
        scale_y = image.height / 810
        left = round(clip["x"] * scale_x)
        top = round(clip["y"] * scale_y)
        right = min(image.width, round((clip["x"] + clip["width"]) * scale_x))
        bottom = min(image.height, round((clip["y"] + clip["height"]) * scale_y))
        if left <= 0 and top <= 0 and right >= image.width and bottom >= image.height:
            return
        cropped = image.crop((left, top, right, bottom))
        cropped.save(path)


def _first_existing_path(candidates: Sequence[Path]) -> Path | None:
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved
    return None


def _find_headless_browser() -> Path | None:
    """查找本机 Chrome/Edge，供没有 Playwright 时的截图兜底使用。"""

    candidates: list[Path] = []
    for command_name in ("msedge.exe", "chrome.exe", "msedge", "chrome"):
        executable = shutil.which(command_name)
        if executable:
            candidates.append(Path(executable))
    for variable_name, relative_path in (
        ("PROGRAMFILES", "Microsoft\\Edge\\Application\\msedge.exe"),
        ("PROGRAMFILES(X86)", "Microsoft\\Edge\\Application\\msedge.exe"),
        ("LOCALAPPDATA", "Microsoft\\Edge\\Application\\msedge.exe"),
        ("PROGRAMFILES", "Google\\Chrome\\Application\\chrome.exe"),
        ("PROGRAMFILES(X86)", "Google\\Chrome\\Application\\chrome.exe"),
        ("LOCALAPPDATA", "Google\\Chrome\\Application\\chrome.exe"),
    ):
        base = os.environ.get(variable_name, "").strip()
        if base:
            candidates.append(Path(base) / relative_path)
    return _first_existing_path(candidates)


def _write_selection_artifacts(
    output_dir: Path,
    selection_run: RepresentativeSelectionRun,
    rows: Sequence[RepresentativeReportRow],
    warnings: Sequence[str],
) -> None:
    selected_results_path = Path(output_dir) / "selected_results.jsonl"
    with selected_results_path.open("w", encoding="utf-8", newline="\n") as handle:
        for selected in selection_run.selected:
            content = selected.candidate.content
            selected_payload = {
                "content": {
                    "row_number": content.row_number,
                    "platform": content.platform,
                    "content_id": content.content_id,
                    "title": content.title,
                    "text": content.text,
                    "author": content.author,
                    "published_at": content.published_at,
                    "content_url": content.content_url,
                    "voice_type": content.voice_type,
                    "sentiment_label": content.sentiment_label,
                    "primary_label": content.primary_label,
                    "secondary_label": content.secondary_label,
                },
                "decision": selected.decision.model_dump(),
            }
            handle.write(json.dumps(selected_payload, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
    report_payload: dict[str, object] = {
        "selected_count": len(selection_run.selected),
        "rows": [
            {
                "platform": row.platform,
                "sentiment": row.sentiment,
                "content_id": row.content_id,
                "content_url": row.content_url,
                "link_text": row.link_text,
                "comment_text": row.comment_text,
                "primary_label": row.primary_label,
                "secondary_label": row.secondary_label,
                "action_advice": row.action_advice,
                "screenshot_path": (
                    None if row.screenshot_path is None else str(row.screenshot_path)
                ),
                "processing_progress": row.processing_progress,
            }
            for row in rows
        ],
        "warnings": list(warnings),
    }
    (Path(output_dir) / "representative_report.json").write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _cell_text(values: tuple[object, ...], index: int) -> str:
    if index >= len(values) or values[index] is None:
        return ""
    return str(values[index]).strip()


def _integer_or_zero(values: tuple[object, ...], index: int | None) -> int:
    if index is None or index >= len(values) or values[index] is None:
        return 0
    try:
        return int(float(str(values[index]).strip()))
    except (TypeError, ValueError):
        return 0


def _platform_text(value: str) -> str:
    compact = "".join(value.split()).casefold()
    if compact in {"douyin", "抖音"}:
        return "抖音"
    if compact in {"xiaohongshu", "小红书"}:
        return "小红书"
    return value


__all__ = ["RepresentativeReportPreparation", "prepare_representative_report"]
