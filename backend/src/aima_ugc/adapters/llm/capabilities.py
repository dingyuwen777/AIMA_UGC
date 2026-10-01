"""已核验的上游并发提示；不修改模型请求、思考模式或业务输出。"""

from urllib.parse import urlsplit


def declared_concurrency(base_url: str, model: str) -> int | None:
    """官方账户默认限额仅作探测上界，未知模型继续通过真实反馈学习。"""
    # 核验于 2026-10-01：https://api-docs.deepseek.com/quick_start/rate_limit/
    # 代理域名不能继承官方额度；多个 API Key 也不能视为不同账户额度。
    if urlsplit(base_url).hostname != "api.deepseek.com":
        return None
    return {"deepseek-flash": 2500, "deepseek-pro": 500}.get(model)
