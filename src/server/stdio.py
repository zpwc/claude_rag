"""
MCP server entry point for the local RAG knowledge base.

Claude Code spawns this process and communicates via stdio JSON-RPC.
IMPORTANT: stdout is reserved for MCP protocol frames — never print() here.
           All logging goes to stderr.
"""

from __future__ import annotations

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))

import asyncio
import json
import logging
import sys

# Force UTF-8 on Windows console before anything else
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Logging to stderr only
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from src.core.config import SERVER_NAME, SERVER_VERSION
from src.core.rag_engine import RAGEngine
from src.server.tools import TOOLS, dispatch

# ── Server setup ───────────────────────────────────────────────────────────

server = Server(
    SERVER_NAME,
    instructions=(
        "这是一个关于海思 Hi3516CV610 芯片 SDK 代码样例和芯片文档知识的知识库，"
        "当需要基于海思 Hi3516CV610 芯片编写代码和查询芯片相关的内容可以使用该知识库。"
        "Hi3516CV610 通常会简称为 CV610 或泛指海思视觉芯片。\n\n"
        "主要工具：\n"
        "• search_knowledge_base / search_docs / search_code — 语义检索文档或代码\n"
        "• search_symbol — 按符号名精确检索（函数/类/宏）\n"
        "• grep_code — 正则全文搜索源文件\n"
        "• get_file / get_chunk_context — 读取完整文件或指定 chunk 的上下文\n"
        "• ingest_document / ingest_directory — 向知识库添加文件\n"
        "• list_documents / list_code_files — 列出已索引内容\n"
        "• delete_document — 从知识库删除文件\n"
        "检索建议：先用 search_knowledge_base 做宽泛语义检索，"
        "再用 grep_code 或 search_symbol 定位具体符号/行号。"
    ),
)

_engine: RAGEngine | None = None


def get_engine() -> RAGEngine:
    global _engine
    if _engine is None:
        _engine = RAGEngine()
    return _engine


# ── Tool definitions & dispatch ────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    logger.info("Tool called: %s  args=%s", name, arguments)
    try:
        result = await dispatch(name, arguments, get_engine())
    except Exception as exc:
        logger.exception("Unhandled error in tool '%s'", name)
        result = {"error": str(exc), "tool": name}

    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    ]


# ── Entry point ────────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("%s v%s starting…", SERVER_NAME, SERVER_VERSION)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    # Windows asyncio: use SelectorEventLoop to avoid ProactorEventLoop issues
    # with some stdin/stdout pipe configurations.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
