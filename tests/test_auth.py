"""
Unit tests for src/server/auth.py — the API-key ASGI auth middleware.

Pure ASGI tests: the middleware is driven directly with hand-built scope /
receive / send, so no HTTP client (httpx) or pytest-asyncio is required —
each async path is run with asyncio.run().
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.server.auth import AuthMiddleware, extract_api_key, is_protected

API_KEY = "s3cret-key-abc"


# ── Test doubles ────────────────────────────────────────────────────────────

class DummyApp:
    """Downstream ASGI app: records whether it was reached and replies 200."""

    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


def http_scope(path, headers=None, query_string=b""):
    return {
        "type": "http",
        "path": path,
        "headers": headers or [],
        "query_string": query_string,
    }


def drive(middleware, scope):
    """Run one request through the middleware; return (status, downstream_app)."""
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(middleware(scope, receive, send))

    status = next(
        (m["status"] for m in sent if m["type"] == "http.response.start"), None
    )
    return status, sent


# ── is_protected ─────────────────────────────────────────────────────────────

class TestIsProtected:
    @pytest.mark.parametrize("path", [
        "/sse",
        "/messages/",
        "/messages/abc123",
        "/api/stats",
        "/api/answer",
        "/api/file/foo.c",
        "/shutdown",
    ])
    def test_protected_paths(self, path):
        assert is_protected(path) is True

    @pytest.mark.parametrize("path", [
        "/health",
        "/ui",
        "/assets/index.js",
        "/static/favicon.ico",
    ])
    def test_public_paths(self, path):
        assert is_protected(path) is False

    def test_unknown_path_is_not_protected(self):
        # 未枚举的路径（如根路径）默认放行
        assert is_protected("/") is False
        assert is_protected("/favicon.ico") is False


# ── extract_api_key ───────────────────────────────────────────────────────────

class TestExtractApiKey:
    def test_from_header(self):
        scope = http_scope("/api/stats", headers=[(b"x-api-key", b"hello")])
        assert extract_api_key(scope) == "hello"

    def test_from_query_param(self):
        scope = http_scope("/sse", query_string=b"api_key=fromquery&foo=bar")
        assert extract_api_key(scope) == "fromquery"

    def test_header_takes_precedence_over_query(self):
        scope = http_scope(
            "/api/stats",
            headers=[(b"x-api-key", b"fromheader")],
            query_string=b"api_key=fromquery",
        )
        assert extract_api_key(scope) == "fromheader"

    def test_missing_returns_none(self):
        assert extract_api_key(http_scope("/api/stats")) is None


# ── AuthMiddleware ─────────────────────────────────────────────────────────────

class TestAuthMiddleware:
    def test_protected_without_key_returns_401(self):
        app = DummyApp()
        mw = AuthMiddleware(app, api_key=API_KEY)
        status, _ = drive(mw, http_scope("/api/stats"))
        assert status == 401
        assert app.called is False

    def test_protected_with_wrong_key_returns_401(self):
        app = DummyApp()
        mw = AuthMiddleware(app, api_key=API_KEY)
        status, _ = drive(
            mw, http_scope("/api/stats", headers=[(b"x-api-key", b"wrong")])
        )
        assert status == 401
        assert app.called is False

    def test_protected_with_correct_header_passes(self):
        app = DummyApp()
        mw = AuthMiddleware(app, api_key=API_KEY)
        status, _ = drive(
            mw, http_scope("/api/stats", headers=[(b"x-api-key", API_KEY.encode())])
        )
        assert status == 200
        assert app.called is True

    def test_protected_with_correct_query_param_passes(self):
        app = DummyApp()
        mw = AuthMiddleware(app, api_key=API_KEY)
        status, _ = drive(
            mw, http_scope("/sse", query_string=f"api_key={API_KEY}".encode())
        )
        assert status == 200
        assert app.called is True

    def test_public_path_passes_without_key(self):
        app = DummyApp()
        mw = AuthMiddleware(app, api_key=API_KEY)
        status, _ = drive(mw, http_scope("/health"))
        assert status == 200
        assert app.called is True

    def test_non_http_scope_passes_through(self):
        app = DummyApp()
        mw = AuthMiddleware(app, api_key=API_KEY)
        # lifespan scope should never be blocked
        status, _ = drive(mw, {"type": "lifespan"})
        assert app.called is True

    def test_empty_server_key_fails_closed(self):
        """启用鉴权但未配置 key 时，受保护路径一律拒绝（即使客户端发空 key）。"""
        app = DummyApp()
        mw = AuthMiddleware(app, api_key="")
        status, _ = drive(
            mw, http_scope("/api/stats", headers=[(b"x-api-key", b"")])
        )
        assert status == 401
        assert app.called is False
