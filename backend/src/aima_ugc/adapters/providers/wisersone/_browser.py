"""WisersOne 网页定位与下载协议；由正式导出适配器调用。"""

from __future__ import annotations

import inspect
import json
import os
import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zipfile import BadZipFile, ZipFile
from zoneinfo import ZoneInfo

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

_LOGIN_PRIMARY = "https://login.wisers.net/?clang=zh_CN-zh_CN&fromUrl=https%3A%2F%2Fwww.wisersone.com&product=wiseone"
_LOGIN_FALLBACK = "https://login.wisers.net/?clang=zh_CN-zh_CN"
_DATACENTER_HOST = "datacenter.wisersone.com"
_RUNTIME_SCHEMA = "wisersone-runtime/v2"
_GROUP_ID = os.environ.get("WISERSONE_GROUP_ID", "AMKJ")
_USER_ID = os.environ.get("WISERSONE_USER_ID", "admin")
_PASSWORD = os.environ.get("WISERSONE_PASSWORD", "")
_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_PROFILE_DIR = _SCRIPT_DIR / "browser-profile"
_DEFAULT_AUTH_STATE = _SCRIPT_DIR / "auth" / "wisersone_state.json"
_DEFAULT_RUNTIME_STATE = _SCRIPT_DIR / "auth" / "wisersone_runtime.json"
_DEFAULT_OUTPUT_DIR = _SCRIPT_DIR / "downloads"
_DEFAULT_DEBUG_DIR = _SCRIPT_DIR / "debug"
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_LINUX_VIEWPORT = {"width": 1920, "height": 1080}


def _log(level: str, message: str) -> None:
    """输出北京时间、真实调用文件和行号，便于服务器排障。"""
    frame = inspect.currentframe()
    caller = frame.f_back if frame else None
    source_name = Path(caller.f_code.co_filename).name if caller else Path(__file__).name
    line = caller.f_lineno if caller else 0
    now = datetime.now(_SHANGHAI).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{now} {source_name} L{line}] [{level.upper()}] {message}")


def _env_bool(name: str, default: bool) -> bool:
    """读取布尔环境变量；未配置时使用给定默认值。"""
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} 必须是 true/false、1/0、yes/no 或 on/off，实际值={raw!r}")


def _resolve_runtime_path(env_name: str, default_path: Path) -> Path:
    """解析运行时路径；相对路径统一相对于脚本目录。"""
    raw = os.environ.get(env_name)
    if not raw:
        return default_path.resolve()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = _SCRIPT_DIR / path
    return path.resolve()


def _is_windows() -> bool:
    """判断当前是否为 Windows。"""
    return os.name == "nt"


def _is_posix_root() -> bool:
    """判断当前是否为 POSIX/Linux root 用户。"""
    return os.name == "posix" and hasattr(os, "geteuid") and (os.geteuid() == 0)


def _browser_runtime_policy() -> dict[str, Any]:
    """返回当前平台的 Chromium 运行策略。

    Windows：
    - 使用 Playwright 自带 Chromium；
    - 默认 headed，便于首次登录和人工验证；
    - sandbox 开启。

    Linux 非 root：
    - 使用 Playwright 自带 Chromium；
    - 默认 headless；
    - sandbox 开启。

    Linux/Docker root：
    - 使用 Playwright 自带 Chromium；
    - 强制 headless；
    - sandbox 关闭，以兼容 root 容器运行。
    """
    if _is_posix_root():
        return {
            "headless": True,
            "chromium_sandbox": False,
            "runtime_mode": "linux_root_chromium_headless",
        }
    default_headless = not _is_windows()
    headless = _env_bool("WISERSONE_HEADLESS", default_headless)
    if _is_windows():
        runtime_mode = "windows_chromium_headless" if headless else "windows_chromium_headed"
    else:
        runtime_mode = "linux_chromium_headless" if headless else "linux_chromium_headed"
    return {"headless": headless, "chromium_sandbox": _is_windows(), "runtime_mode": runtime_mode}


def _browser_launch_kwargs() -> tuple[dict[str, Any], str]:
    """把当前策略转换为 Playwright Chromium launch 参数。"""
    policy = _browser_runtime_policy()
    kwargs: dict[str, Any] = {
        "headless": bool(policy["headless"]),
        "chromium_sandbox": bool(policy["chromium_sandbox"]),
    }
    return (kwargs, str(policy["runtime_mode"]))


def _context_kwargs() -> dict[str, Any]:
    """返回 BrowserContext 参数；Windows 保持 headed Chromium 的普通页面环境。"""
    kwargs: dict[str, Any] = {"accept_downloads": True}
    if not _is_windows():
        kwargs.update(
            {"viewport": _LINUX_VIEWPORT, "locale": "zh-CN", "timezone_id": "Asia/Shanghai"}
        )
    return kwargs


def _storage_state_is_valid(path: Path) -> bool:
    """检查 Playwright storage state 是否具备基本可用结构。"""
    if not path.is_file():
        return False
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return False
    return (
        isinstance(state, dict)
        and isinstance(state.get("cookies"), list)
        and isinstance(state.get("origins"), list)
    )


def _save_storage_state_atomic(context: Any, auth_state_path: Path) -> None:
    """原子保存登录状态；Playwright 支持时同时导出 IndexedDB。"""
    auth_state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = auth_state_path.with_name(auth_state_path.name + ".tmp")
    try:
        try:
            context.storage_state(path=str(tmp_path), indexed_db=True)
        except TypeError:
            context.storage_state(path=str(tmp_path))
        state = json.loads(tmp_path.read_text(encoding="utf-8"))
        if not (
            isinstance(state, dict)
            and isinstance(state.get("cookies"), list)
            and isinstance(state.get("origins"), list)
        ):
            raise RuntimeError("Playwright 导出的登录状态结构无效")
        os.replace(tmp_path, auth_state_path)
        if os.name == "posix":
            os.chmod(auth_state_path, 384)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _parse_datacenter_home(url: str) -> tuple[str, str | None] | None:
    """解析 WisersOne 数据中心 home URL。

    关键事实：
    - 登录后服务端可能停在 ``/home``；
    - 也可能进入 ``/home/<monitor_id>``；
    - 因此 URL 是否包含 monitor_id 不能作为“是否登录成功”的判断条件。
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme.lower() != "https":
        return None
    if (parsed.hostname or "").lower() != _DATACENTER_HOST:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if not parts or parts[0].lower() != "home":
        return None
    if len(parts) == 1:
        return (f"https://{_DATACENTER_HOST}/home", None)
    monitor_id = parts[1]
    if not re.fullmatch("[A-Za-z0-9_-]+", monitor_id):
        return None
    return (f"https://{_DATACENTER_HOST}/home/{monitor_id}", monitor_id)


def _load_runtime_state(runtime_state_path: Path) -> dict[str, Any] | None:
    """读取并校验上一次自动发现的 WisersOne 业务入口。

    兼容旧版 v1 中的 ``monitor_id``，但不再把它解释成页面按钮 value。
    """
    if not runtime_state_path.is_file():
        return None
    try:
        payload = json.loads(runtime_state_path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        _log("WARN", f"运行时入口文件不可用，将重新自动发现: {runtime_state_path}")
        return None
    if not isinstance(payload, dict):
        return None
    home_url = payload.get("home_url")
    if not isinstance(home_url, str):
        return None
    parsed = _parse_datacenter_home(home_url)
    if parsed is None:
        return None
    normalized_home, parsed_home_id = parsed
    home_id = payload.get("home_id")
    if not isinstance(home_id, str):
        legacy_id = payload.get("monitor_id")
        home_id = legacy_id if isinstance(legacy_id, str) else parsed_home_id
    if parsed_home_id is not None:
        home_id = parsed_home_id
    return {"schema": _RUNTIME_SCHEMA, "home_url": normalized_home, "home_id": home_id}


def _save_runtime_state_atomic(
    runtime_state_path: Path, *, home_url: str, home_id: str | None
) -> None:
    """原子保存 WisersOne 业务入口。

    ``home_id`` 仅表示 URL 路由中的 ``/home/<id>``，不再假定它是
    页面中某个 ``button[value]`` 的值。
    """
    parsed = _parse_datacenter_home(home_url)
    if parsed is None:
        raise RuntimeError(f"拒绝保存无效 WisersOne home URL: {home_url!r}")
    normalized_home, parsed_home_id = parsed
    if parsed_home_id is not None:
        home_id = parsed_home_id
    runtime_state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = runtime_state_path.with_name(runtime_state_path.name + ".tmp")
    payload = {"schema": _RUNTIME_SCHEMA, "home_url": normalized_home, "home_id": home_id}
    try:
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2)
            + """
""",
            encoding="utf-8",
        )
        os.replace(tmp_path, runtime_state_path)
        if os.name == "posix":
            os.chmod(runtime_state_path, 384)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _find_datacenter_page(context: Any, preferred_page: Page, *, timeout: int = 120000) -> Any:
    """等待登录完成并进入 WisersOne 数据中心 home。

    ``/home`` 与 ``/home/<monitor_id>`` 都视为已成功进入数据中心。
    """
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        pages = list(context.pages)
        if preferred_page in pages:
            pages.remove(preferred_page)
            pages.insert(0, preferred_page)
        for candidate in pages:
            parsed = _parse_datacenter_home(candidate.url)
            if parsed is not None:
                home_url, url_monitor_id = parsed
                return (candidate, home_url, url_monitor_id)
        time.sleep(0.25)
    urls = [candidate.url for candidate in context.pages]
    raise RuntimeError(f"WisersOne 登录后未进入数据中心 home。当前页面={urls!r}")


def _stabilize_datacenter_home(
    page: Page, *, initial_home_url: str, timeout: int = 5000
) -> tuple[str, str | None]:
    """短暂等待 WisersOne SPA 把 ``/home`` 更新成更具体的 ``/home/<id>``。

    若 5 秒内没有更具体 URL，也接受 ``/home``，因为它本身已经是合法
    数据中心入口；不再扫描页面上所有监测项目猜测一个 ID。
    """
    best = _parse_datacenter_home(initial_home_url)
    if best is None:
        raise RuntimeError(f"无效的数据中心入口: {initial_home_url!r}")
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        current = _parse_datacenter_home(page.url)
        if current is not None:
            best = current
            if current[1] is not None:
                return current
        page.wait_for_timeout(250)
    return best


def _dismiss_known_page_overlays(page: Page) -> None:
    """关闭已知的 WisersOne 网页内引导弹层。

    Chromium 的“保存密码”气泡属于浏览器 UI，不是网页 DOM；它不是本次
    locator timeout 的原因。这里处理的是会真实拦截网页点击的
    “常用筛选方案”等 DOM 弹层。
    """
    guide_title = page.get_by_text("常用筛选方案", exact=True).filter(visible=True)
    if not guide_title.count():
        return
    for label in ("跳过", "关闭", "知道了", "以后再说"):
        candidate = page.get_by_text(label, exact=True).filter(visible=True)
        if candidate.count():
            try:
                candidate.first.click(timeout=3000)
                page.wait_for_timeout(300)
                if not guide_title.count():
                    return
            except Exception:
                pass
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    except Exception:
        pass


def _wait_business_page_ready(page: Page, *, timeout: int = 120000) -> None:
    """等待当前监测业务页达到脚本真正需要的可操作状态。"""
    _dismiss_known_page_overlays(page)
    _date_filter_button(page).wait_for(state="visible", timeout=timeout)


def _fill_login_field(frame: Any, value: str, tokens: tuple[str, ...], fallback_index: int) -> bool:
    """根据标签和 HTML 元数据填写登录输入框。"""
    inputs = frame.locator("input:visible")
    candidates: list[int] = []
    for index in range(inputs.count()):
        field = inputs.nth(index)
        metadata = field.evaluate("""element => ({
                type: element.type,
                name: element.name,
                id: element.id,
                placeholder: element.placeholder,
                ariaLabel: element.getAttribute('aria-label'),
                parentText: element.parentElement?.innerText || ''
            })""")
        haystack = " ".join(str(item or "") for item in metadata.values()).lower()
        if metadata["type"] != "password" and any(token in haystack for token in tokens):
            field.fill(value)
            return True
        if metadata["type"] != "password":
            candidates.append(index)
    if candidates:
        field_index = candidates[min(fallback_index, len(candidates) - 1)]
        inputs.nth(field_index).fill(value)
        return True
    return False


_GROUP_FIELD_TOKENS = ("group", "集团", "机构", "组织", "企业", "company", "tenant")
_USER_FIELD_TOKENS = ("user", "用户名", "账号", "帐户", "登录名", "userid", "login")


def _find_account_login_frame(page: Page, *, timeout: int) -> Any:
    """等待账号登录表单；若当前停在微信登录，则自动切到“账号登录”。"""
    deadline = time.monotonic() + timeout / 1000
    switched_tab = False
    while time.monotonic() < deadline:
        for frame in page.frames:
            password = frame.locator('input[type="password"]:visible')
            if password.count():
                return frame
        if not switched_tab:
            for frame in page.frames:
                account_tab = frame.get_by_text("账号登录", exact=True).filter(visible=True)
                if account_tab.count():
                    try:
                        account_tab.first.click(timeout=3000)
                        switched_tab = True
                        break
                    except Exception:
                        continue
        time.sleep(0.25)
    return None


def _wait_login_finished(page: Page, *, allow_manual: bool) -> None:
    """等待离开登录域；headed 环境允许必要时人工完成验证。"""
    try:
        page.wait_for_function(
            "() => !window.location.hostname.includes('login.wisers.net')", timeout=60000
        )
        return
    except PlaywrightTimeoutError:
        if not allow_manual:
            raise RuntimeError(
                "WisersOne 登录未在 60 秒内完成；当前为 headless 环境，无法人工处理验证码/扫码。"
            ) from None
    _log("WARN", "自动登录 60 秒内未完成；浏览器保持打开，如页面要求人工验证，请在 5 分钟内完成。")
    try:
        page.wait_for_function(
            "() => !window.location.hostname.includes('login.wisers.net')", timeout=5 * 60000
        )
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("WisersOne 5 分钟内仍未完成登录。") from exc


def _saved_login_form_ready(frame: Any) -> bool:
    """仅判断网站保存的账号表单是否完整，不将密码值读取到 Python。"""
    password = frame.locator('input[type="password"]:visible')
    account_fields = frame.locator(
        'input[type="text"]:visible, input[type="email"]:visible, input:not([type]):visible'
    )
    return (
        bool(password.count())
        and password.first.evaluate("input => Boolean(input.value)")
        and account_fields.evaluate_all(
            "inputs => inputs.length >= 2 && inputs.every(input => Boolean(input.value.trim()))"
        )
    )


def _submit_account_login_form(login_frame: Any) -> None:
    """提交当前账号表单，保留网站自动填写的已保存凭证。"""
    login_name = re.compile("^\\s*(?:登录|登錄|login|sign\\s*in)\\s*$", re.IGNORECASE)
    login_buttons = login_frame.get_by_role("button", name=login_name)
    login_button = next(
        (
            login_buttons.nth(index)
            for index in range(login_buttons.count())
            if login_buttons.nth(index).is_visible()
        ),
        None,
    )
    if login_button is None:
        submit_buttons = login_frame.locator(
            'button[type="submit"]:visible, input[type="submit"]:visible'
        )
        login_button = submit_buttons.first if submit_buttons.count() else None
    if login_button is None:
        raise RuntimeError("WisersOne 登录页未找到提交按钮")
    login_button.click()


def _login_if_needed(page: Page, *, allow_manual: bool) -> None:
    """优先复用会话或网站保存的表单；缺少凭证时提示更新认证。"""
    if "login.wisers.net" not in page.url:
        return
    login_frame = _find_account_login_frame(page, timeout=12000)
    if login_frame is None and _parse_datacenter_home(page.url) is not None:
        return
    if login_frame is None:
        _log("WARN", "当前登录页未挂载账号表单，使用纯登录入口恢复加载一次。")
        page.goto(_LOGIN_FALLBACK, wait_until="load")
        login_frame = _find_account_login_frame(page, timeout=30000)
    if login_frame is None and _parse_datacenter_home(page.url) is not None:
        return
    if login_frame is None:
        if allow_manual:
            _log("INFO", "仍未找到账号表单；浏览器保持可见，等待人工登录，最长 5 分钟。")
            try:
                page.wait_for_function(
                    "() => !window.location.hostname.includes('login.wisers.net')",
                    timeout=5 * 60000,
                )
                return
            except PlaywrightTimeoutError as exc:
                raise RuntimeError("WisersOne 登录页面未正常挂载，且人工登录未完成。") from exc
        raise RuntimeError(
            "WisersOne 登录页面未正常挂载账号表单；当前 Linux/headless 环境无法人工处理。"
        )
    if not _PASSWORD:
        if _saved_login_form_ready(login_frame):
            _log("INFO", "使用网站已保存的账号表单恢复登录会话。")
            _submit_account_login_form(login_frame)
            _wait_login_finished(page, allow_manual=allow_manual)
            return
        if not allow_manual:
            raise RuntimeError(
                "WisersOne 登录态缺失或已失效；请使用 --headed 重新登录，"
                "然后迁移更新后的运行态认证目录。"
            )
        _log(
            "INFO", "请在浏览器中完成人工登录（最长 5 分钟）；成功后自动保存登录态，无需保存密码。"
        )
        try:
            page.wait_for_function(
                "() => !window.location.hostname.includes('login.wisers.net')", timeout=5 * 60000
            )
            return
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("5 分钟内未完成人工登录；请重新运行并在浏览器中登录。") from exc
    visible_inputs = login_frame.locator("input:visible")
    visible_inputs.first.wait_for(state="visible", timeout=30000)
    if not _fill_login_field(login_frame, _GROUP_ID, _GROUP_FIELD_TOKENS, 0):
        raise RuntimeError("WisersOne 登录页未找到 Group ID 输入框")
    if not _fill_login_field(login_frame, _USER_ID, _USER_FIELD_TOKENS, 1):
        raise RuntimeError("WisersOne 登录页未找到 User ID 输入框")
    password = login_frame.locator('input[type="password"]:visible').first
    password.fill(_PASSWORD)
    _submit_account_login_form(login_frame)
    _wait_login_finished(page, allow_manual=allow_manual)


def _ensure_authenticated(
    context: Any, page: Page, *, runtime_state_path: Path, allow_manual: bool
) -> Any:
    """恢复/建立登录态，并确认 WisersOne 真实业务页已经可操作。"""
    runtime_state = _load_runtime_state(runtime_state_path)
    if runtime_state is not None:
        page.goto(str(runtime_state["home_url"]), wait_until="domcontentloaded")
    else:
        page.goto(_LOGIN_PRIMARY, wait_until="domcontentloaded")
    _login_if_needed(page, allow_manual=allow_manual)
    try:
        home_page, home_url, url_home_id = _find_datacenter_page(context, page, timeout=120000)
    except RuntimeError:
        if runtime_state is None:
            raise
        _log("WARN", "已保存的 WisersOne home 无法继续使用，将从登录入口重新发现。")
        page.goto(_LOGIN_PRIMARY, wait_until="domcontentloaded")
        _login_if_needed(page, allow_manual=allow_manual)
        home_page, home_url, url_home_id = _find_datacenter_page(context, page, timeout=120000)
    home_url, home_id = _stabilize_datacenter_home(
        home_page, initial_home_url=home_url, timeout=5000
    )
    _save_runtime_state_atomic(runtime_state_path, home_url=home_url, home_id=home_id)
    _wait_business_page_ready(home_page, timeout=120000)
    return (home_page, home_url, home_id)


def _write_chromium_profile_preferences(profile_dir: Path) -> None:
    """关闭 Chromium 密码保存提示，同时保留 Profile 中其他已有偏好。

    该提示属于浏览器 UI，不属于网页 DOM。关闭密码保存服务可以消除
    “要保存 login.wisers.net 的密码吗？”弹窗这一干扰变量。
    """
    preferences_path = profile_dir / "Default" / "Preferences"
    preferences_path.parent.mkdir(parents=True, exist_ok=True)
    preferences: dict[str, Any] = {}
    if preferences_path.is_file():
        try:
            loaded = json.loads(preferences_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                preferences = loaded
        except OSError, json.JSONDecodeError:
            _log(
                "WARN",
                "Chromium Preferences 无法解析；为保护现有 Profile，本次不覆盖该文件。",
            )
            return
    preferences["credentials_enable_service"] = False
    preferences["credentials_enable_autosignin"] = False
    profile_preferences = preferences.get("profile")
    if not isinstance(profile_preferences, dict):
        profile_preferences = {}
        preferences["profile"] = profile_preferences
    profile_preferences["password_manager_enabled"] = False
    tmp_path = preferences_path.with_name(preferences_path.name + ".tmp")
    try:
        tmp_path.write_text(
            json.dumps(preferences, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        os.replace(tmp_path, preferences_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _open_context(
    playwright: Any, profile_dir: Path, auth_state_path: Path, *, headless: bool | None = None
) -> Any:
    """打开浏览器上下文；跨机器 auth state 优先，首次运行使用持久 Profile。"""
    auth_valid = _storage_state_is_valid(auth_state_path)
    launch_kwargs, runtime_mode = _browser_launch_kwargs()
    if headless is not None:
        launch_kwargs["headless"] = headless
    context_kwargs = _context_kwargs()
    if auth_valid:
        browser = playwright.chromium.launch(**launch_kwargs)
        try:
            context = browser.new_context(storage_state=str(auth_state_path), **context_kwargs)
        except Exception:
            browser.close()
            raise
        return (browser, context, "auth_state", bool(launch_kwargs["headless"]), runtime_mode)
    profile_dir.mkdir(parents=True, exist_ok=True)
    _write_chromium_profile_preferences(profile_dir)
    persistent_kwargs = dict(launch_kwargs)
    persistent_kwargs.update(context_kwargs)
    context = playwright.chromium.launch_persistent_context(str(profile_dir), **persistent_kwargs)
    return (None, context, "browser_profile", bool(launch_kwargs["headless"]), runtime_mode)


def _safe_click(
    locator: Any, description: str, *, timeout: int = 30000, center: bool = True
) -> None:
    """等待、居中滚动并正常点击目标，不使用 force=True 掩盖真实遮挡。"""
    try:
        locator.wait_for(state="visible", timeout=timeout)
        if center:
            locator.evaluate("""element => element.scrollIntoView({
                    block: 'center',
                    inline: 'center',
                    behavior: 'instant'
                })""")
            locator.page.wait_for_timeout(150)
        locator.click(timeout=timeout)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(f"页面操作失败：{description}") from exc


def _read_checkbox_state(checkbox: Locator) -> bool | None:
    """在 DOM 能表达状态时读取 checkbox 当前是否已选中。"""
    try:
        return checkbox.is_checked()
    except Exception:
        pass
    aria_checked = checkbox.get_attribute("aria-checked")
    if aria_checked in ("true", "false"):
        return aria_checked == "true"
    data_state = checkbox.get_attribute("data-state")
    if data_state in ("checked", "unchecked"):
        return data_state == "checked"
    return None


def _select_monitor_folders(page: Page, folder_names: tuple[str, ...]) -> None:
    """按原“公司品牌”交互方式依次选择多个监测文件夹。"""
    for folder_name in folder_names:
        found = False
        for frame in page.frames:
            label = frame.get_by_text(folder_name, exact=True).filter(visible=True).first
            try:
                label.wait_for(state="visible", timeout=30000)
            except PlaywrightTimeoutError:
                continue
            row = label.locator("xpath=ancestor::li[1]")
            if row.count() == 0:
                row = label.locator("xpath=ancestor::*[.//button or @role='checkbox'][1]")
            if row.count() == 0:
                row = label.locator("xpath=..")
            row.scroll_into_view_if_needed()
            try:
                label.hover(timeout=3000)
                page.wait_for_timeout(100)
            except Exception:
                pass
            checkbox = row.locator(
                '[role="checkbox"]:visible, input[type="checkbox"]:visible, '
                "button[aria-checked]:visible"
            ).first
            if checkbox.count():
                checked = _read_checkbox_state(checkbox)
                if checked is not True:
                    _safe_click(
                        checkbox, f"选择监测文件夹“{folder_name}”", timeout=30000, center=False
                    )
                found = True
                break
            box = row.bounding_box()
            if box and box["width"] > 0 and (box["height"] > 0):
                row.click(
                    position={
                        "x": min(31, max(1, box["width"] - 1)),
                        "y": max(1, box["height"] / 2),
                    },
                    timeout=30000,
                )
            else:
                _safe_click(row, f"选择监测文件夹“{folder_name}”", timeout=30000)
            found = True
            break
        if not found:
            raise RuntimeError(f"WisersOne 页面未找到可见的监测文件夹: {folder_name}")


def _date_filter_button(page: Page) -> Any:
    """定位当前日期筛选，兼容已有预设和旧的自定义日期显示。"""
    return (
        page.get_by_role(
            "button",
            name=re.compile(
                "^\\s*(?:今天|昨天|过去\\s*\\d+\\s*(?:小时|天|周|个?月)|\\d{4}[-/年].*)\\s*$"
            ),
        )
        .filter(visible=True)
        .first
    )


def _select_last_24_hours(page: Page) -> None:
    """每次重新选择网页的滚动 24 小时预设，避免复用昨天或旧的固定日期。"""
    button = _date_filter_button(page)
    _safe_click(button, "打开日期筛选", center=True)
    preset_name = re.compile("^\\s*过去\\s*24\\s*小时\\s*$")
    preset = page.get_by_text(preset_name, exact=True).filter(visible=True).last
    _safe_click(preset, "选择“过去 24 小时”")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if preset_name.fullmatch(button.inner_text().strip()):
            _log("INFO", "日期筛选已设置为“过去 24 小时”。")
            return
        page.wait_for_timeout(100)
    raise RuntimeError("日期筛选未切换到“过去 24 小时”，停止导出。")


def _field_checkbox_for_value(field_panel: Locator, value: str) -> Any:
    """定位 ``button[value]`` 对应的实际勾选按钮。

    当前真实 DOM 中：
    - ``button[value="content"]`` 等是字段标签按钮；
    - 真正的 checkbox 是紧邻其后的无 ``value`` 小按钮；
    - 两者在视觉上重叠，所以不能再从 value 按钮内部寻找 SVG，也不能直接
      点击 value 按钮来代替 checkbox。
    """
    value_button = field_panel.locator(f'button[value="{value}"]').first
    value_button.wait_for(state="visible", timeout=30000)
    sibling = value_button.locator("xpath=following-sibling::button[1]")
    if sibling.count():
        candidate = sibling.first
        sibling_value = candidate.get_attribute("value")
        if not sibling_value:
            return (value_button, candidate)
    parent = value_button.locator("xpath=..")
    candidates = parent.locator("button:not([value])")
    value_box = value_button.bounding_box()
    if value_box:
        vx1 = value_box["x"]
        vy1 = value_box["y"]
        vx2 = vx1 + value_box["width"]
        vy2 = vy1 + value_box["height"]
        for index in range(candidates.count()):
            candidate = candidates.nth(index)
            if not candidate.is_visible():
                continue
            box = candidate.bounding_box()
            if not box:
                continue
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            if vx1 <= cx <= vx2 and vy1 <= cy <= vy2:
                return (value_button, candidate)
    raise RuntimeError(f"WisersOne 下载字段存在，但未找到对应的 checkbox: value={value!r}")


def _checkbox_is_selected(checkbox: Locator, *, value_button: Locator | None = None) -> bool:
    """读取下载字段 checkbox 的真实选中状态。"""
    aria_checked = checkbox.get_attribute("aria-checked")
    if aria_checked in ("true", "false"):
        return aria_checked == "true"
    data_state = checkbox.get_attribute("data-state")
    if data_state in ("checked", "unchecked"):
        return data_state == "checked"
    if checkbox.locator("svg").count():
        return True
    if value_button is not None and value_button.is_disabled():
        return True
    return False


def _field_value_is_selected(field_panel: Locator, value: str) -> bool:
    """读取指定 ``button[value]`` 对应字段是否已选中。"""
    value_button, checkbox = _field_checkbox_for_value(field_panel, value)
    return _checkbox_is_selected(checkbox, value_button=value_button)


def _set_value_button_selected(
    page: Page, field_panel: Locator, value: str, selected: bool, *, timeout: int = 10000
) -> None:
    """通过实际 checkbox 把下载字段归一化到目标状态。"""
    value_button, checkbox = _field_checkbox_for_value(field_panel, value)
    current = _checkbox_is_selected(checkbox, value_button=value_button)
    if current == selected:
        return
    _safe_click(
        checkbox,
        f"设置下载字段 {value}={('选中' if selected else '未选中')}",
        timeout=timeout,
        center=False,
    )
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        current = _checkbox_is_selected(checkbox, value_button=value_button)
        if current == selected:
            return
        page.wait_for_timeout(100)
    raise RuntimeError(f"WisersOne 下载字段状态未按预期更新: value={value!r}, selected={selected}")


def _group_button_is_selected(group_button: Locator) -> bool:
    """读取“全部字段”组按钮自身的选中状态。

    当前真实 DOM 已确认：DocsRelatedAll / AccountRelatedAll 等组按钮本身就是
    toggle，它们后面直接跟第一个字段按钮，并不存在独立 checkbox。
    组按钮选中状态继续兼容 aria/data-state，并以内部 SVG 作为当前页面兜底。
    """
    aria_checked = group_button.get_attribute("aria-checked")
    if aria_checked in ("true", "false"):
        return aria_checked == "true"
    data_state = group_button.get_attribute("data-state")
    if data_state in ("checked", "unchecked"):
        return data_state == "checked"
    return group_button.locator("svg").count() > 0


def _set_group_button_selected(
    page: Page, field_panel: Locator, value: str, selected: bool, *, timeout: int = 10000
) -> None:
    """把“全部字段”组按钮归一化到目标状态。

    与普通字段不同，这里直接点击 ``button[value="<GroupAll>"]`` 本身；
    不再尝试寻找不存在的独立 checkbox。
    """
    group_button = field_panel.locator(f'button[value="{value}"]').first
    group_button.wait_for(state="visible", timeout=timeout)
    current = _group_button_is_selected(group_button)
    _log(
        "INFO",
        f"下载字段组 {value}：selected={current}",
    )
    if current == selected:
        return
    _safe_click(
        group_button,
        f"设置下载字段组 {value}={('选中' if selected else '未选中')}",
        timeout=timeout,
        center=False,
    )
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        current = _group_button_is_selected(group_button)
        if current == selected:
            return
        page.wait_for_timeout(100)
    raise RuntimeError(
        f"WisersOne 下载字段组状态未按预期更新: value={value!r}, expected_selected={selected}"
    )


def _selected_download_field_values(field_panel: Locator) -> set[str]:
    """基于每个字段实际 checkbox 读取当前选中 value 集合。"""
    selected: set[str] = set()
    value_buttons = field_panel.locator("button[value]")
    for index in range(value_buttons.count()):
        value_button = value_buttons.nth(index)
        value = value_button.get_attribute("value")
        if not value:
            continue
        try:
            if _field_value_is_selected(field_panel, value):
                selected.add(value)
        except RuntimeError:
            continue
    return selected


def _log_download_field_state(field_panel: Locator, values: tuple[str, ...], *, label: str) -> None:
    """打印目标下载字段的 label/checkbox 关联与选中状态。"""
    for value in values:
        button = field_panel.locator(f'button[value="{value}"]').first
        if not button.count():
            _log("WARN", f"[下载字段诊断:{label}] value={value!r} 不存在")
            continue
        try:
            value_button, checkbox = _field_checkbox_for_value(field_panel, value)
            _log(
                "INFO",
                f"下载字段 {value} ({label})："
                f"selected={_checkbox_is_selected(checkbox, value_button=value_button)}",
            )
        except Exception as exc:
            _log("WARN", f"[下载字段诊断:{label}] value={value!r}; error={exc!r}")


def _configure_download_fields(page: Page) -> None:
    """把 WisersOne 下载字段归一化为脚本要求的精确集合。

    真实 DOM 分为两类控件：
    1. ``*RelatedAll``：“全部字段”组按钮本身就是 toggle；
    2. 普通字段：``button[value]`` 是字段标签，真正 checkbox 是独立小按钮。

    两类控件分别操作，最终仍按目标字段集合做严格校验。
    """
    field_header = page.get_by_text("下载字段选择", exact=True).filter(visible=True)
    field_panel = field_header.locator("xpath=../../../..")
    field_panel.locator('button[value="no"]').wait_for(state="visible", timeout=30000)
    desired_fields = {
        "no",
        "folder_name",
        "md5_doc_id",
        "headline",
        "content",
        "media_name",
        "section",
        "pub_time",
        "media_type_id",
        "author",
        "sentiment_type_name",
        "doc_url",
        "fans_cnt",
    }
    group_values = (
        "DocsRelatedAll",
        "AccountRelatedAll",
        "InterectiveRelatedAll",
        "CommentRelatedAll",
    )
    diagnostic_values = (*tuple(sorted(desired_fields)),)
    _log_download_field_state(field_panel, diagnostic_values, label="before")
    for group_value in group_values:
        group_button = field_panel.locator(f'button[value="{group_value}"]')
        if not group_button.count():
            _log("WARN", f"下载字段组未出现在当前 DOM，跳过: {group_value}")
            continue
        _set_group_button_selected(page, field_panel, group_value, False)
    for field_value in ("content", "fans_cnt"):
        _set_value_button_selected(page, field_panel, field_value, True)
    page.wait_for_timeout(300)
    selected_fields = _selected_download_field_values(field_panel)
    _log_download_field_state(field_panel, diagnostic_values, label="after")
    selected_fields.difference_update(group_values)
    if selected_fields != desired_fields:
        missing = sorted(desired_fields - selected_fields)
        unexpected = sorted(selected_fields - desired_fields)
        raise RuntimeError(
            f"WisersOne 下载字段与要求不一致: missing={missing!r}, unexpected={unexpected!r}"
        )


def _find_export_entry_button(page: Page) -> Locator:
    """定位导出入口；优先语义识别，最后才兼容原 Codegen 的第 7 个 icon-button。"""
    icon_buttons = page.locator('button[data-testid="icon-button"]:visible')
    metadata: list[dict[str, Any]] = []
    semantic_indexes: list[int] = []
    for index in range(icon_buttons.count()):
        button = icon_buttons.nth(index)
        item = button.evaluate("""el => ({
                text: (el.innerText || '').trim(),
                ariaLabel: el.getAttribute('aria-label'),
                title: el.getAttribute('title'),
                value: el.getAttribute('value'),
                dataTestId: el.getAttribute('data-testid'),
            })""")
        metadata.append({"index": index, **item})
        haystack = " ".join(str(item.get(key) or "") for key in ("text", "ariaLabel", "title"))
        if re.search("(导出|export)", haystack, re.IGNORECASE):
            semantic_indexes.append(index)
    _log("INFO", f"导出入口候选 icon-button 数量={len(metadata)}")
    if len(semantic_indexes) == 1:
        index = semantic_indexes[0]
        _log("INFO", f"根据按钮语义识别导出入口: icon-button[{index}]")
        return icon_buttons.nth(index)
    if icon_buttons.count() > 6:
        _log(
            "WARN",
            "未能唯一识别导出入口，按已验证的页面结构使用第 7 个 icon-button。",
        )
        return icon_buttons.nth(6)
    raise RuntimeError("WisersOne 页面无法识别导出入口")


def _field_panel_is_expanded(page: Page) -> bool:
    """判断下载字段面板是否已经展开到可配置状态。"""
    field_header = page.get_by_text("下载字段选择", exact=True).filter(visible=True)
    if not field_header.count():
        return False
    try:
        field_panel = field_header.locator("xpath=../../../..")
        return field_panel.locator('button[value="no"]:visible').count() > 0
    except Exception:
        return False


def _open_download_field_panel(page: Page) -> None:
    """打开下载字段面板；兼容“已经展开”和多种展开控件结构。"""
    page.wait_for_timeout(500)
    if _field_panel_is_expanded(page):
        _log("INFO", "下载字段面板已经处于展开状态，跳过“展开”点击。")
        return
    candidate_builders: tuple[Callable[[], Locator], ...] = (
        lambda: page.get_by_role("button", name="展开", exact=True),
        lambda: page.locator("button:visible").filter(has_text=re.compile("^\\s*展开\\s*$")),
        lambda: page.locator('[role="button"]:visible').filter(
            has_text=re.compile("^\\s*展开\\s*$")
        ),
        lambda: page.locator('[aria-label="展开"]:visible'),
        lambda: page.locator('[title="展开"]:visible'),
        lambda: page.get_by_text("展开", exact=True).filter(visible=True),
    )
    for builder in candidate_builders:
        candidate = builder()
        if not candidate.count():
            continue
        target = candidate.first
        _log("INFO", "发现“展开”候选，尝试点击。")
        try:
            _safe_click(target, "展开下载字段", timeout=10000)
        except Exception as exc:
            _log("WARN", f"“展开”候选点击失败，继续尝试其他候选: {exc!r}")
            continue
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if _field_panel_is_expanded(page):
                _log("INFO", "下载字段面板已成功展开。")
                return
            page.wait_for_timeout(200)
    raise RuntimeError("WisersOne 导出入口已点击，但找不到可用的“展开”控件或下载字段面板。")


def _validate_and_publish_xlsx(partial: Path, destination: Path) -> None:
    """检查 XLSX 包完整性后原子发布；不读取或判断业务数据内容。"""
    try:
        with ZipFile(partial) as package:
            required = {"[Content_Types].xml", "xl/workbook.xml"}
            if not required.issubset(package.namelist()) or package.testzip() is not None:
                raise RuntimeError("下载文件不是完整的 XLSX 包。")
        partial.replace(destination)
    except (BadZipFile, OSError) as exc:
        raise RuntimeError("下载文件无法作为 XLSX 打开或保存。") from exc


def _save_xlsx_body(body: bytes, destination: Path) -> None:
    """以临时文件保存下载内容，校验成功后再生成最终 XLSX。"""
    partial = destination.with_suffix(".xlsx.part")
    try:
        partial.write_bytes(body)
        _validate_and_publish_xlsx(partial, destination)
    finally:
        partial.unlink(missing_ok=True)


def _download_api_json(context: Any, url: str, headers: dict[str, str]) -> Any:
    """复用网页实际请求读取下载状态；暂时失败可重试，认证和契约错误明确报错。"""
    try:
        response = context.request.get(url, headers=headers, timeout=60000)
    except PlaywrightTimeoutError:
        raise
    except PlaywrightError:
        _log("WARN", "下载任务查询网络连接失败，继续等待并重试。")
        return None
    try:
        if response.status in (401, 403):
            raise RuntimeError("WisersOne 下载请求被拒绝或登录态已失效；请重新登录更新 auth 目录。")
        if response.status in (429, 500, 502, 503, 504):
            _log("WARN", f"下载任务查询暂时不可用（HTTP {response.status}），继续等待并重试。")
            return None
        if not 200 <= response.status < 300:
            raise RuntimeError(f"WisersOne 下载接口失败（HTTP {response.status}）。")
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("WisersOne 下载接口未返回有效 JSON。") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            raise RuntimeError("WisersOne 下载接口返回异常；请检查登录态与网站任务状态。")
        return payload["data"]
    finally:
        response.dispose()


def _read_download_task(context: Any, list_url: str, headers: dict[str, str], task_id: str) -> Any:
    """从真实列表接口逐页查找本次任务，不能把其他已完成任务当作成功。"""
    parsed = urlparse(list_url)
    params = dict(parse_qsl(parsed.query))
    offset = 0
    while True:
        params.update(offset=str(offset), limit="8")
        url = urlunparse(parsed._replace(query=urlencode(params)))
        data = _download_api_json(context, url, headers)
        if data is None:
            return None
        items, total = (data.get("items"), data.get("total"))
        if not isinstance(items, list) or not isinstance(total, int):
            raise RuntimeError("下载任务列表结构已变化，无法确认本次任务。")
        for item in items:
            if not isinstance(item, dict):
                raise RuntimeError("下载任务记录格式异常。")
            if item.get("task_id") == task_id:
                return item
        offset += len(items)
        if not items or offset >= total:
            raise RuntimeError("下载任务列表中未找到本次任务；可能已被删除，请检查网站下载记录。")
