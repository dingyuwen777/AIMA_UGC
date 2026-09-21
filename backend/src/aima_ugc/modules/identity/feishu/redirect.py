"""`return_to` 站内白名单：**只允许站内相对路径**。

════════ 为什么必须有这一层 ════════

登录流程会用 `return_to` 决定"授权成功后把浏览器送到哪里"：

    /api/v1/auth/feishu/login?return_to=/some/page
    → 授权成功 → 302 到 return_to

如果原样使用用户传来的值，就得到一个**开放重定向（open redirect）**：

    ?return_to=https://evil.example/phish
    → 用户从**我们的域名**被送到钓鱼站，地址栏一开始还是我们

这类漏洞常被用来伪装钓鱼链接（"你看链接是 aima 的域名"）。
所以判定必须 **fail closed**：拿不准的一律不当作站内路径。

════════ 为什么判定这么啰嗦 ════════

浏览器对 URL 的解析有很多"等价写法"，只判 `startswith("/")` 会被绕过：

| 绕过形态 | 为什么危险 |
|---|---|
| `//evil.example` | **协议相对 URL** —— 浏览器会跳到 `https://evil.example` |
| `/\evil.example` | 浏览器把反斜杠当 `/`，等价于上面那条 |
| `/%2f%2fevil.example` | 编码斜杠，解码后变成 `//evil.example` |
| `/path\r\nSet-Cookie:` | **CRLF 注入**，可污染响应头 |
| `https://evil.example` | 绝对 URL，直接跳外站 |
| `javascript:alert(1)` | 伪协议 |

所以判定的顺序是：**先逐类拒绝，最后才用 `urlsplit` 复核**（双重保险）。

════════ 与 `safe_return_to` 的分工 ════════

- `is_safe_return_to` —— **纯判定**，返回布尔值（测试与调用方都能直接用）。
- `safe_return_to` —— **判定 + 兜底**，不安全时退回默认值。
  登录端点用它：**不安全的输入不报错，只是"退回首页"** ——
  对正常用户来说，一个手改坏的 `return_to` 不该让登录失败。
"""

from __future__ import annotations

from urllib.parse import urlsplit

# 默认回跳目标：站内首页。
DEFAULT_RETURN_TO = "/"

# 控制字符：CRLF 注入的载体，也可能被用于绕过某些解析器。
_CONTROL_CHARS = (
    "\r",
    "\n",
    "\t",
    "\x00",
    # Unicode 行分隔符：某些解析器视作换行。
    "\u2028",
    "\u2029",
)

# 编码斜杠的常见写法（大小写都算）。解码后等价于 "/"，用来伪造 `//host`。
_ENCODED_SLASHES = ("%2f", "%5c")


def is_safe_return_to(value: str | None) -> bool:
    """判断 `return_to` 是否是**安全的站内相对路径**；拿不准一律 `False`。

    判定要点（顺序即优先级，任意一条不满足就拒绝）：

    1. 必须是非空字符串，且不以控制字符污染；
    2. 必须以**单个** `/` 开头 —— `//` 是协议相对 URL，会跳到别的站；
    3. 不含反斜杠 —— 浏览器把 `\\` 当 `/`；
    4. 不含编码斜杠（`%2f` / `%5c`）—— 解码后会变成 `//host`；
    5. 用 `urlsplit` 复核：解析后**没有 scheme 也没有 netloc**。

    第 5 条是前 4 条的兜底：即使将来出现没想到的写法，
    "解析后带 scheme/netloc" 这条也能拦住。
    """

    if not value or not isinstance(value, str):
        return False

    candidate = value.strip()
    if not candidate:
        return False
    if any(char in candidate for char in _CONTROL_CHARS):
        return False
    # 必须以单个 "/" 开头："//" 是协议相对 URL，浏览器会跳到别的站。
    if not candidate.startswith("/") or candidate.startswith("//"):
        return False
    # 浏览器把反斜杠当 "/"，`/\evil.com` 等价于 `//evil.com`。
    if "\\" in candidate:
        return False
    lowered = candidate.lower()
    if any(token in lowered for token in _ENCODED_SLASHES):
        return False

    parts = urlsplit(candidate)
    return not (parts.scheme or parts.netloc)


def safe_return_to(value: str | None, *, default: str = DEFAULT_RETURN_TO) -> str:
    """校验并返回安全的 `return_to`；不安全就退回 `default`（**绝不原样返回**）。"""

    candidate = value.strip() if isinstance(value, str) else ""
    return candidate if is_safe_return_to(candidate) else default


__all__ = [
    "DEFAULT_RETURN_TO",
    "is_safe_return_to",
    "safe_return_to",
]
