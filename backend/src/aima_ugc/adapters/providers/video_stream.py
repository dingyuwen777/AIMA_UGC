"""受控 CDN 视频流：固定公网连接地址，逐跳校验，不保存媒体字节。"""

from __future__ import annotations

import ipaddress
import re
import socket
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

_VIDEO_ORIGINS = frozenset({"sns-v11.rednotecdn.com", "sns-v27.rednotecdn.com"})
_RANGE = re.compile(r"bytes=(\d*)-(\d*)\Z")
_CONTENT_RANGE = re.compile(r"bytes (?:(\d+)-(\d+)|(\*))/(\d+)\Z")
_MAX_BYTES = 512 * 1024 * 1024
# getaddrinfo 没有可取消超时；超时后仍在运行的调用占住独立配额，不能无限派生线程。
_DNS_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="aima-video-dns")
_DNS_SLOTS = threading.BoundedSemaphore(4)
_OPEN_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="aima-video-open")
_OPEN_SLOTS = threading.BoundedSemaphore(16)


def _bounded_result[T](
    *,
    pool: ThreadPoolExecutor,
    slots: threading.BoundedSemaphore,
    task: Callable[[], T],
    timeout: float,
    late_cleanup: Callable[[T], None] | None = None,
) -> T:
    """调用方有硬等待上限；迟到结果只释放资源，不回到已经结束的请求。"""
    if timeout <= 0:
        raise VideoStreamError("cdn_timeout")
    if not slots.acquire(blocking=False):
        raise VideoStreamError("busy")
    abandoned = threading.Event()
    try:
        future = pool.submit(task)
    except BaseException:
        slots.release()
        raise

    def finish(completed: Future[T]) -> None:
        try:
            if (
                abandoned.is_set()
                and late_cleanup is not None
                and not completed.cancelled()
                and completed.exception() is None
            ):
                late_cleanup(completed.result())
        finally:
            slots.release()

    future.add_done_callback(finish)
    try:
        return future.result(timeout=timeout)
    except BaseException as exc:
        abandoned.set()
        # 完成回调可能刚好早于 abandoned；此时仍须处理已返回但无人拥有的响应。
        if (
            late_cleanup is not None
            and future.done()
            and not future.cancelled()
            and future.exception() is None
        ):
            late_cleanup(future.result())
        if isinstance(exc, FutureTimeout):
            raise VideoStreamError("cdn_timeout") from exc
        raise


class VideoStreamError(RuntimeError):
    """只暴露分类，异常文本不包含签名地址或上游响应。"""

    def __init__(self, code: str, *, upstream_status: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.upstream_status = upstream_status


def normalize_video_url(value: str) -> str:
    """仅两个本轮已验证的视频 Origin 允许从 HTTP 规范化为 HTTPS。"""
    if (
        len(value) > 8192
        or any(ord(char) <= 32 or ord(char) == 127 for char in value)
        or "\\" in value
    ):
        raise VideoStreamError("invalid_source")
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in _VIDEO_ORIGINS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or parsed.port not in {None, 443}
            or not parsed.path.startswith("/")
        ):
            raise ValueError
    except ValueError as exc:
        raise VideoStreamError("invalid_source") from exc
    return urlunsplit(("https", str(parsed.hostname), parsed.path, parsed.query, ""))


def validate_video_range(value: str | None) -> str | None:
    """仅支持单段 bytes Range，避免多段响应与无界整数解析。"""
    if value is None:
        return None
    match = _RANGE.fullmatch(value) if len(value) <= 128 else None
    if match is None or not any(match.groups()):
        raise VideoStreamError("invalid_range")
    start, end = match.groups()
    if (
        any(len(part) > 19 for part in (start, end))
        or (start and end and int(start) > int(end))
        or (not start and int(end) == 0)
    ):
        raise VideoStreamError("invalid_range")
    return value


def _default_client() -> httpx.Client:
    # 每个流独占 Client，关闭浏览器请求即可释放其连接，不影响其他 viewer。
    return httpx.Client(
        timeout=httpx.Timeout(connect=5, read=15, write=5, pool=2),
        follow_redirects=False,
        trust_env=False,
        transport=httpx.HTTPTransport(retries=0),
    )


class VideoStreamHandle:
    """持有一个上游响应和连接配额，所有退出路径均可幂等关闭。"""

    def __init__(
        self,
        *,
        response: httpx.Response,
        client: httpx.Client,
        release: Callable[[], None],
        failure: Callable[[str], None] | None,
        bytes_per_second: int,
    ) -> None:
        self.status_code = response.status_code
        self.headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
        if response.status_code != 416:
            self.headers["Content-Type"] = "video/mp4"
        for name in ("Content-Range", "Accept-Ranges"):
            value = response.headers.get(name)
            if value is not None:
                self.headers[name] = value
        self.headers["Content-Length"] = (
            "0" if response.status_code == 416 else response.headers.get("Content-Length", "")
        )
        if not self.headers["Content-Length"]:
            del self.headers["Content-Length"]
        self._response, self._client, self._release = response, client, release
        self._failure = failure
        self._bytes_per_second = bytes_per_second
        self._expected_bytes: int | None
        content_range = response.headers.get("Content-Range")
        if response.status_code == 206 and content_range is not None:
            matched = _CONTENT_RANGE.fullmatch(content_range)
            assert matched is not None
            self._expected_bytes = int(matched.group(2)) - int(matched.group(1)) + 1
        else:
            length = self.headers.get("Content-Length")
            self._expected_bytes = int(length) if length is not None else None
        self._closed = threading.Event()
        self._close_lock = threading.Lock()

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    def close(self) -> None:
        """断开、416、迭代失败与正常结束共用释放路径。"""
        with self._close_lock:
            if self.closed:
                return
            self._closed.set()
            try:
                self._response.close()
            finally:
                try:
                    self._client.close()
                finally:
                    self._release()

    def iter_bytes(self) -> Iterator[bytes]:
        """按流限速并限制持续时长；取消时停止等待和读取。"""
        started, count = time.monotonic(), 0
        try:
            if self.status_code == 416:
                return
            for chunk in self._response.iter_bytes(chunk_size=64 * 1024):
                if self.closed:
                    return
                count += len(chunk)
                if self._expected_bytes is not None and count > self._expected_bytes:
                    raise VideoStreamError("cdn_invalid_response")
                elapsed = time.monotonic() - started
                if count > _MAX_BYTES or elapsed > 300:
                    raise VideoStreamError("stream_limit")
                delay = count / self._bytes_per_second - elapsed
                if delay > 0 and self._closed.wait(delay):
                    return
                yield chunk
            if (
                not self.closed
                and self._expected_bytes is not None
                and count != self._expected_bytes
            ):
                raise VideoStreamError("cdn_invalid_response")
        except (httpx.HTTPError, VideoStreamError) as exc:
            # 浏览器主动关闭不污染共享源状态，也不触发另一个 viewer 的刷新。
            if not self.closed:
                code = (
                    "cdn_timeout"
                    if isinstance(exc, httpx.TimeoutException)
                    else (exc.code if isinstance(exc, VideoStreamError) else "cdn_network_error")
                )
                if self._failure is not None:
                    self._failure(code)
                raise VideoStreamError(code) from None
        finally:
            self.close()


class VideoStreamProxy:
    """全进程与逐 Principal 配额共同限制连接数及总带宽上界。"""

    def __init__(
        self,
        *,
        max_connections: int = 16,
        per_principal_connections: int = 4,
        bytes_per_second: int = 4 * 1024 * 1024,
        resolve: Callable[..., Any] = socket.getaddrinfo,
        client_factory: Callable[[], httpx.Client] = _default_client,
        dns_timeout_seconds: float = 5,
        open_timeout_seconds: float = 20,
    ) -> None:
        self._maximum = max_connections
        self._per_principal = per_principal_connections
        self._bytes_per_second = bytes_per_second
        self._resolve, self._client_factory = resolve, client_factory
        self._dns_timeout, self._open_timeout = dns_timeout_seconds, open_timeout_seconds
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(self._counts.values())

    def _acquire(self, principal_id: str) -> Callable[[], None]:
        with self._lock:
            count = self._counts.get(principal_id, 0)
            if sum(self._counts.values()) >= self._maximum or count >= self._per_principal:
                raise VideoStreamError("busy")
            self._counts[principal_id] = count + 1

        def release() -> None:
            with self._lock:
                count = self._counts[principal_id] - 1
                if count:
                    self._counts[principal_id] = count
                else:
                    del self._counts[principal_id]

        return release

    def _pinned_url(self, url: str, *, deadline: float) -> tuple[str, str]:
        parsed = urlsplit(url)
        host = str(parsed.hostname)
        try:
            answers = _bounded_result(
                pool=_DNS_POOL,
                slots=_DNS_SLOTS,
                task=lambda: self._resolve(host, 443, type=socket.SOCK_STREAM),
                timeout=min(self._dns_timeout, deadline - time.monotonic()),
            )
            addresses = [ipaddress.ip_address(answer[4][0]) for answer in answers]
        except (OSError, ValueError) as exc:
            raise VideoStreamError("invalid_source") from exc
        if not addresses or any(
            not address.is_global
            or address.is_multicast
            or address.is_reserved
            or getattr(address, "is_site_local", False)
            or getattr(address, "ipv4_mapped", None) is not None
            for address in addresses
        ):
            raise VideoStreamError("invalid_source")
        address = addresses[0]
        ip_host = f"[{address}]" if address.version == 6 else str(address)
        return urlunsplit(("https", ip_host, parsed.path, parsed.query, "")), host

    def open(
        self,
        source_url: str,
        *,
        principal_id: str,
        byte_range: str | None = None,
        failure: Callable[[str], None] | None = None,
    ) -> VideoStreamHandle:
        """调用方先完成 Principal、Content 可见性和会话校验，禁止传入用户 URL。"""
        current = normalize_video_url(source_url)
        deadline = time.monotonic() + self._open_timeout
        byte_range = validate_video_range(byte_range)
        release = self._acquire(principal_id)
        client: httpx.Client | None = None
        response: httpx.Response | None = None
        try:
            for hop in range(4):
                pinned, host = self._pinned_url(current, deadline=deadline)
                if client is None:
                    client = self._client_factory()
                headers = {"Host": host, "Accept": "video/mp4", "Accept-Encoding": "identity"}
                if byte_range is not None:
                    headers["Range"] = byte_range
                request = client.build_request(
                    "GET", pinned, headers=headers, extensions={"sni_hostname": host}
                )
                # HTTP Client 可能自动保留重定向响应的 Cookie；媒体链路始终不携带凭据。
                for credential in ("Cookie", "Authorization", "Proxy-Authorization"):
                    request.headers.pop(credential, None)
                active_client = client

                def send(
                    owner: httpx.Client = active_client,
                    outbound: httpx.Request = request,
                ) -> httpx.Response:
                    return owner.send(outbound, stream=True, follow_redirects=False)

                response = _bounded_result(
                    pool=_OPEN_POOL,
                    slots=_OPEN_SLOTS,
                    task=send,
                    timeout=deadline - time.monotonic(),
                    late_cleanup=lambda late: late.close(),
                )
                status = response.status_code
                if status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    response.close()
                    # 相同 IP 的不同 CDN Host 也必须重新 TLS 握手并验证新主机名。
                    client.close()
                    client = None
                    if location is None or hop == 3:
                        raise VideoStreamError("invalid_source")
                    current = normalize_video_url(urljoin(current, location))
                    continue
                if status not in {200, 206, 416}:
                    code = {
                        403: "cdn_forbidden",
                        404: "cdn_not_found",
                        410: "cdn_gone",
                        429: "cdn_rate_limited",
                    }.get(status, "cdn_unavailable" if status >= 500 else "cdn_rejected")
                    raise VideoStreamError(code, upstream_status=status)
                _validate_response_range(response, byte_range)
                if (
                    status != 416
                    and response.headers.get("Content-Encoding", "identity").lower() != "identity"
                ):
                    raise VideoStreamError("cdn_invalid_response")
                if (
                    status != 416
                    and response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    != "video/mp4"
                ):
                    raise VideoStreamError("unsupported_format")
                length = response.headers.get("Content-Length")
                if length is not None and (
                    not length.isascii()
                    or not length.isdigit()
                    or len(length) > 10
                    or int(length) > _MAX_BYTES
                ):
                    raise VideoStreamError("stream_limit")
                if response.headers.get("Accept-Ranges") not in {None, "bytes", "none"}:
                    raise VideoStreamError("cdn_invalid_response")
                return VideoStreamHandle(
                    response=response,
                    client=client,
                    release=release,
                    failure=failure,
                    bytes_per_second=self._bytes_per_second,
                )
            raise VideoStreamError("invalid_source")
        except (httpx.HTTPError, VideoStreamError) as exc:
            _close_failed_stream(response, client, release)
            error = (
                exc
                if isinstance(exc, VideoStreamError)
                else VideoStreamError(
                    "cdn_timeout"
                    if isinstance(exc, httpx.TimeoutException)
                    else "cdn_network_error"
                )
            )
            if failure is not None and error.code.startswith("cdn_"):
                failure(error.code)
            raise error from None
        except BaseException:
            _close_failed_stream(response, client, release)
            raise


def _validate_response_range(response: httpx.Response, requested: str | None) -> None:
    """校验实际表示的边界、总长、请求区间与长度；200 降级保持真实状态。"""
    value = response.headers.get("Content-Range")
    if response.status_code == 200:
        if value is not None:
            raise VideoStreamError("cdn_invalid_response")
        return
    match = _CONTENT_RANGE.fullmatch(value) if value is not None and len(value) <= 128 else None
    if match is None or any(len(part) > 19 for part in match.groups() if part is not None):
        raise VideoStreamError("cdn_invalid_response")
    start, end, unsatisfied, raw_total = match.groups()
    total = int(raw_total)
    if response.status_code == 416:
        if unsatisfied is None:
            raise VideoStreamError("cdn_invalid_response")
        return
    if unsatisfied is not None or requested is None or total <= 0:
        raise VideoStreamError("cdn_invalid_response")
    assert start is not None and end is not None
    first, last = int(start), int(end)
    if first > last or last >= total:
        raise VideoStreamError("cdn_invalid_response")
    wanted = _RANGE.fullmatch(requested)
    assert wanted is not None
    wanted_start, wanted_end = wanted.groups()
    expected_first = int(wanted_start) if wanted_start else max(0, total - int(wanted_end))
    expected_last = min(int(wanted_end), total - 1) if wanted_start and wanted_end else total - 1
    if first != expected_first or last != expected_last:
        raise VideoStreamError("cdn_invalid_response")
    length = response.headers.get("Content-Length")
    if length is not None and (
        len(length) > 19
        or not length.isascii()
        or not length.isdigit()
        or int(length) != last - first + 1
    ):
        raise VideoStreamError("cdn_invalid_response")


def _close_failed_stream(
    response: httpx.Response | None,
    client: httpx.Client | None,
    release: Callable[[], None],
) -> None:
    """关闭异常也不能阻止其他资源与配额释放。"""
    try:
        if response is not None:
            response.close()
    finally:
        try:
            if client is not None:
                client.close()
        finally:
            release()
