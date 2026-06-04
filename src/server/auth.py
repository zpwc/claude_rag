"""
SSE / REST API 鉴权中间件（共享 API Key 方案）。

纯 ASGI 中间件（非 Starlette BaseHTTPMiddleware）——这样才能正确覆盖通过
`Mount` 挂载的 MCP 子应用（`/messages/`）和 SSE 长连接（`/sse`），
BaseHTTPMiddleware 会缓冲响应、破坏流式传输。

启用条件由 serve.py 控制（config.AUTH_ENABLED）。受保护路径需携带：
  • 请求头 `x-api-key: <key>`，或
  • 查询参数 `?api_key=<key>`（用于无法自定义请求头的客户端，如浏览器 EventSource）

公开路径（始终放行）：/health、/ui、/assets/*、/static/*
受保护路径：/sse、/messages/、/api/*、/shutdown

Stdio 模式不经过 HTTP 层，因此完全不受影响。
"""

from __future__ import annotations

import secrets
from urllib.parse import parse_qs

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# 受保护路径前缀：命中其一即需要校验 API key
PROTECTED_PREFIXES = ("/sse", "/messages/", "/api/", "/shutdown")

# 公开路径：始终放行（优先级高于受保护前缀）
PUBLIC_EXACT = ("/health", "/ui")
PUBLIC_PREFIXES = ("/assets/", "/static/")


def is_protected(path: str) -> bool:
    """判断路径是否需要鉴权。公开路径优先放行；其余按受保护前缀匹配。"""
    if path in PUBLIC_EXACT:
        return False
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return False
    return any(path == p or path.startswith(p) for p in PROTECTED_PREFIXES)


def extract_api_key(scope: Scope) -> str | None:
    """从 ASGI scope 提取 API key：先查 `x-api-key` 头，再回退 `api_key` 查询参数。"""
    # 1) x-api-key 请求头（headers 是 [(bytes, bytes), ...]，名字已小写）
    for name, value in scope.get("headers", []):
        if name == b"x-api-key":
            try:
                return value.decode("latin-1")
            except Exception:
                return None

    # 2) ?api_key=xxx 查询参数回退
    qs = scope.get("query_string", b"")
    if qs:
        params = parse_qs(qs.decode("latin-1"))
        values = params.get("api_key")
        if values:
            return values[0]

    return None


class AuthMiddleware:
    """纯 ASGI 中间件：对受保护路径校验共享 API key，不匹配返回 401。"""

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        self.app = app
        self.api_key = api_key or ""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # 非 HTTP 流量（lifespan / websocket 握手）直接放行
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not is_protected(path):
            await self.app(scope, receive, send)
            return

        provided = extract_api_key(scope)

        # 未配置服务端 key 时一律拒绝（fail closed）；常量时间比较防时序侧信道
        ok = bool(self.api_key) and provided is not None and secrets.compare_digest(
            provided, self.api_key
        )
        if not ok:
            response = JSONResponse(
                {"error": "unauthorized", "detail": "missing or invalid api key"},
                status_code=401,
                headers={"WWW-Authenticate": "ApiKey"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
