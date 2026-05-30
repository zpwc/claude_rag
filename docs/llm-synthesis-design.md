# RAG WebUI — LLM 综合层 + 重排 + 混合检索增强方案

## 背景

当前 WebUI 止步于"检索"——向量检索后直接把原始 chunk 列表展示给用户，缺乏 LLM 合成答案。
用户体验与 Claude Code 的差距在于：MCP 工具检索到 chunk 后 Claude 会阅读并综合，WebUI 要补上这一环。

**目标：**
1. **LLM 综合层**：检索 → 重排 → LLM 流式生成答案（上方），原始 chunk 作引用（下方）
2. **多 Provider**：DeepSeek / Qianwen / Ollama / Anthropic / OpenAI 通过环境变量切换
3. **重排**：CrossEncoder 对 top-20 结果重排，送 top-5 给 LLM
4. **混合检索增强**：为 text collection 补 BM25（目前只有 code 有 BM25+RRF）
5. **展示优化**：同文档 chunk 分组、代码高亮、低相关度过滤

---

## 架构总览

```
用户输入 → InputBar ["✨ AI 回答"] → POST /api/answer
                                           │
                                ┌──────────▼──────────┐
                                │   RAGEngine.search() │  向量检索 top-20
                                │   + BM25 (text+code) │  RRF 融合
                                └──────────┬──────────┘
                                           │ 20 chunks
                                ┌──────────▼──────────┐
                                │    Reranker          │  CrossEncoder 重排
                                │  cross-encoder/      │  top-20 → top-5
                                │  mmarco-mMiniLMv2    │
                                └──────────┬──────────┘
                                           │ 5 chunks
                          ┌────────────────▼────────────────┐
                          │         LLMSynthesizer          │
                          │  OpenAI-compat (DeepSeek/Qwen)  │
                          │  or Anthropic SDK               │
                          └────────────────┬────────────────┘
                                           │  SSE stream
                              ┌────────────▼───────────────┐
                              │  {"type":"results", ...}   │ → 立即显示 chunk 卡片
                              │  {"type":"delta","text":""}│ → 流式填充 LLM 答案
                              │  {"type":"done", ...}      │
                              └────────────────────────────┘
```

---

## SSE 流协议（/api/answer）

```
event data 顺序：
1. {"type":"results",  "data": [reranked_chunks...]}   # 立刻渲染 chunk 列表
2. {"type":"delta",    "text": "根据"}                  # LLM 逐 token 流出
3. {"type":"delta",    "text": "知识库中..."}
   ...
4. {"type":"done",     "provider":"deepseek","model":"deepseek-chat"}
5. (error) {"type":"error", "message":"..."}
```

前端处理逻辑：
- 收到 `results`：立即渲染 chunk 卡片（用户可直接查看引用）
- 收到 `delta`：追加到 LLM 答案文本框，逐字流出
- 收到 `done`/`error`：停止 loading 动画

---

## 文件清单

### 新建
| 文件 | 说明 |
|------|------|
| `src/core/reranker.py` | CrossEncoder 重排器，懒加载，model 可配置 |
| `src/server/synthesis.py` | 多 Provider LLM 流式综合 |
| `docs/llm-synthesis-design.md` | 本文档 |

### 修改
| 文件 | 改动 |
|------|------|
| `src/core/config.py` | 增加 LLM / Reranker 相关常量 |
| `src/core/rag_engine.py` | text collection 补 BM25+RRF；新增 `search_with_rerank()` |
| `src/server/ui.py` | 新增 `POST /api/answer` SSE endpoint |
| `requirements.txt` | 增加 `openai>=1.0.0` |
| `webui/src/stores/chat.js` | 新增 `answer()` streaming action |
| `webui/src/components/InputBar.vue` | 新增 "✨ AI 回答" 按钮 |
| `webui/src/components/MessageBubble.vue` | 支持 llmAnswer + results 混合展示 |
| `webui/src/components/SearchResult.vue` | 分组展示 + 代码高亮 + 低分过滤 |

---

## 配置说明

项目根目录新建 `.env` 文件（参考 `.env.example`）：

```bash
# Provider 选择: deepseek | qianwen | ollama | claude | openai | custom
SYNTHESIS_BACKEND=deepseek

# API Key（各 provider 通用字段，也可使用 provider 专属环境变量）
LLM_API_KEY=sk-xxx

# 模型名（留空则使用 provider 内置默认值，见下表）
LLM_MODEL=

# 自定义 Base URL（SYNTHESIS_BACKEND=custom 时填写）
LLM_BASE_URL=

# 最大生成 token 数
LLM_MAX_TOKENS=1024

# 重排开关（关闭可加快响应速度）
USE_RERANKING=true
RERANKER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
RERANK_FETCH_K=20   # 初步检索候选数量
RERANK_FINAL_K=5    # 重排后送给 LLM 的数量
```

### 各 Provider 内置默认值

| Provider | Base URL | 默认模型 |
|----------|----------|---------|
| `deepseek` | `https://api.deepseek.com` | `deepseek-chat` |
| `qianwen` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| `ollama` | `http://localhost:11434/v1` | `qwen2.5:7b` |
| `openai` | (官方默认) | `gpt-4o-mini` |
| `claude` | (官方默认) | `claude-haiku-4-5` |
| `custom` | 由 `LLM_BASE_URL` 指定 | 由 `LLM_MODEL` 指定 |

DeepSeek、Qianwen、Ollama 均兼容 OpenAI 协议，统一使用 `openai` SDK。
Anthropic Claude 使用独立 `anthropic` SDK。

---

## 详细实现

### 1. `src/core/config.py` 增加

```python
# ── LLM Synthesis ─────────────────────────────────────────────────────
SYNTHESIS_BACKEND = os.getenv("SYNTHESIS_BACKEND", "")
LLM_API_KEY       = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL      = os.getenv("LLM_BASE_URL", "")
LLM_MODEL         = os.getenv("LLM_MODEL", "")
LLM_MAX_TOKENS    = int(os.getenv("LLM_MAX_TOKENS", "1024"))

# ── Reranking ──────────────────────────────────────────────────────────
USE_RERANKING  = os.getenv("USE_RERANKING", "true").lower() == "true"
RERANKER_MODEL = os.getenv("RERANKER_MODEL",
                     "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
RERANK_FETCH_K = int(os.getenv("RERANK_FETCH_K", "20"))
RERANK_FINAL_K = int(os.getenv("RERANK_FINAL_K", "5"))
```

---

### 2. `src/core/reranker.py`（新建）

```python
from .config import RERANKER_MODEL, RERANK_FINAL_K

class Reranker:
    """懒加载 CrossEncoder，首次 rerank() 时初始化模型。"""

    def __init__(self, model_name: str = RERANKER_MODEL):
        self._model_name = model_name
        self._model = None

    def _ensure_loaded(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name)

    def rerank(self, query: str, docs: list[dict],
               top_k: int = RERANK_FINAL_K) -> list[dict]:
        """对 docs 按与 query 的相关性重新打分，返回 top_k。"""
        self._ensure_loaded()
        pairs = [(query, d["content"][:512]) for d in docs]
        scores = self._model.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [{**d, "rerank_score": round(float(s), 4)}
                for d, s in ranked[:top_k]]
```

---

### 3. `src/core/rag_engine.py` 扩展

**新增方法 `search_with_rerank()`：**
```python
def search_with_rerank(
    self, query: str,
    fetch_k: int = RERANK_FETCH_K,
    final_k: int = RERANK_FINAL_K,
    reranker=None,
) -> list[dict]:
    """向量检索 fetch_k 个候选 → CrossEncoder 重排 → 返回 final_k。"""
    candidates = self.search(query, top_k=fetch_k)
    if reranker and len(candidates) > 1:
        return reranker.rerank(query, candidates, top_k=final_k)
    return candidates[:final_k]
```

**text collection 补 BM25（`search_docs()` 升级）：**

参考 `search_code()` 的实现模式：
- 增加 `self._text_bm25_index: BM25Index | None = None`
- `search_docs()` 改为 hybrid：先向量检索 `BM25_TOP_K` 个，再 BM25 检索，最后 RRF 合并
- `ingest_document()` 对 text 文件入库后重置 `self._text_bm25_index = None`

---

### 4. `src/server/synthesis.py`（新建）

```python
PROVIDER_DEFAULTS = {
    "deepseek": {"base_url": "https://api.deepseek.com",                            "model": "deepseek-chat"},
    "qianwen":  {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",  "model": "qwen-plus"},
    "ollama":   {"base_url": "http://localhost:11434/v1",                           "model": "qwen2.5:7b"},
    "openai":   {"base_url": None,                                                  "model": "gpt-4o-mini"},
    "claude":   {"base_url": None,                                                  "model": "claude-haiku-4-5"},
}

RAG_SYSTEM_PROMPT = """你是专业的技术知识库助手。基于提供的上下文回答问题。
规则：
1. 只使用上下文中的信息，不编造
2. 引用来源时使用 [文件名] 格式
3. 代码片段保留原始格式
4. 信息不足时明确说明"""

class LLMSynthesizer:
    """统一多 Provider 流式综合。OpenAI-compat 走 openai SDK，Anthropic 单独处理。"""

    def __init__(self):
        self._backend = SYNTHESIS_BACKEND
        self._client = None  # 懒加载

    def _ensure_client(self):
        if self._client: return
        defaults = PROVIDER_DEFAULTS.get(self._backend, {})
        base_url = LLM_BASE_URL or defaults.get("base_url")
        api_key  = LLM_API_KEY or "ollama"
        if self._backend == "claude":
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        else:
            import openai
            self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def stream(self, query: str, docs: list[dict]):
        """yield SSE 行，格式: 'data: {...}\\n\\n'"""
        self._ensure_client()
        model = LLM_MODEL or PROVIDER_DEFAULTS.get(self._backend, {}).get("model", "")
        context = _build_context(docs)  # 拼接 [1] doc_name: content

        try:
            if self._backend == "claude":
                # Anthropic SDK streaming
                async with self._client.messages.stream(
                    model=model, max_tokens=LLM_MAX_TOKENS,
                    system=RAG_SYSTEM_PROMPT,
                    messages=[{"role":"user","content":f"问题：{query}\n\n上下文：\n{context}"}],
                ) as s:
                    async for event in s:
                        if event.type == "content_block_delta":
                            yield _sse(type="delta", text=event.delta.text)
            else:
                # OpenAI-compat streaming（DeepSeek/Qwen/Ollama/OpenAI）
                stream = await self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": RAG_SYSTEM_PROMPT},
                        {"role": "user",   "content": f"问题：{query}\n\n上下文：\n{context}"},
                    ],
                    max_tokens=LLM_MAX_TOKENS,
                    stream=True,
                )
                async for chunk in stream:
                    text = chunk.choices[0].delta.content or ""
                    if text:
                        yield _sse(type="delta", text=text)

            yield _sse(type="done", provider=self._backend, model=model)

        except Exception as e:
            yield _sse(type="error", message=str(e))
```

---

### 5. `src/server/ui.py` 新增路由

```python
async def handle_answer(request: Request) -> StreamingResponse:
    """POST /api/answer — 检索 + 重排 + LLM 流式答案（SSE）。"""
    engine = _engine(request)
    body   = await request.json()
    query  = (body.get("query") or "").strip()
    if not query:
        return JSONResponse({"error": "query is required"}, status_code=400)

    async def event_stream():
        # Step 1: 检索 + 重排
        reranker = Reranker() if USE_RERANKING else None
        docs = engine.search_with_rerank(query, reranker=reranker)
        yield _sse(type="results", data=docs)   # 前端立刻渲染 chunk 卡片

        # Step 2: LLM 流式综合
        if not SYNTHESIS_BACKEND:
            yield _sse(type="error", message="SYNTHESIS_BACKEND not configured")
            return
        synthesizer = LLMSynthesizer()
        async for chunk in synthesizer.stream(query, docs):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# 加入 UI_ROUTES：
Route("/api/answer", endpoint=handle_answer, methods=["POST"]),
```

---

### 6. `webui/src/stores/chat.js` 新增 `answer()` action

```javascript
async function answer(query) {
  addMessage('user', query)
  loading.value = true

  // 创建助手消息占位，支持流式更新
  if (!current.value) newSession()
  const msg = {
    role: 'assistant', content: '', results: null,
    llmAnswer: '', isStreaming: true, ts: Date.now()
  }
  current.value.messages.push(msg)

  try {
    const resp = await fetch('/api/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    })

    const reader = resp.body.getReader()
    const dec = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const lines = dec.decode(value).split('\n')
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const event = JSON.parse(line.slice(6))
        if (event.type === 'results') {
          msg.results = event.data          // 触发 Vue 重渲染，chunk 卡片立即显示
        } else if (event.type === 'delta') {
          msg.llmAnswer += event.text       // 逐字追加
        } else if (event.type === 'done' || event.type === 'error') {
          if (event.type === 'error') msg.content = `错误：${event.message}`
          msg.isStreaming = false
          loading.value = false
        }
      }
    }
  } catch (e) {
    msg.content = `请求失败：${e.message}`
    msg.isStreaming = false
    loading.value = false
  }
  persist()
}
```

---

### 7. `webui/src/components/InputBar.vue` 新增按钮

```html
<button class="btn answer" :disabled="!query.trim() || store.loading"
        @click="submit('answer')">
  ✨ AI 回答
</button>
```

`submit()` 中新增分支：`if (mode === 'answer') await store.answer(q)`

---

### 8. `webui/src/components/MessageBubble.vue` 混合展示

```vue
<div v-if="msg.role === 'assistant'" class="bubble">
  <!-- LLM 综合答案（流式渲染） -->
  <div v-if="msg.llmAnswer || msg.isStreaming" class="llm-answer">
    <div class="llm-label">✨ AI 回答</div>
    <div class="llm-text">
      {{ msg.llmAnswer }}
      <span v-if="msg.isStreaming" class="cursor">▋</span>
    </div>
    <div v-if="msg.results?.length" class="divider">参考来源</div>
  </div>
  <!-- 原始 chunk 引用列表 -->
  <SearchResult v-if="msg.results" :results="msg.results"
                @view-file="$emit('view-file', $event)" />
  <!-- 纯文字回复（精准/语义搜索模式） -->
  <div v-else-if="msg.content" class="text">{{ msg.content }}</div>
</div>
```

CSS 新增：
- `.llm-answer`：浅蓝背景，14px，1.7 行高，`white-space: pre-wrap`
- `.cursor`：0.7s blink 动画
- `.divider`：灰色小标题分割线

---

### 9. `webui/src/components/SearchResult.vue` 展示优化

**① 按文档分组**
```javascript
const grouped = computed(() => {
  const map = {}
  for (const r of props.results) {
    if (!map[r.doc_name]) map[r.doc_name] = []
    map[r.doc_name].push(r)
  }
  // 每组按 score 降序
  for (const k of Object.keys(map))
    map[k].sort((a, b) => (b.rerank_score ?? b.score) - (a.rerank_score ?? a.score))
  return map
})
```

每个文档组：显示最高分 chunk，其余折叠为"+ N 个片段"。

**② 代码高亮**

复用 `FileDrawer.vue` 中已有的 `highlighted(content, fileType)` 函数（hljs），
将 `<pre>{{ r.content }}</pre>` 改为 `<pre v-html="highlighted(r.content, r.file_type)" />`。

**③ 低相关度标记**

`score < 0.3` 的卡片添加 `class="low-relevance"`：`opacity: 0.55` + 灰色"低相关度"标签。

**④ source_path 副标题**

在 `doc_name` 下方以 `font-size: 11px; color: #aaa` 显示 `r.source_path`。

---

## 新增依赖

```
# requirements.txt
openai>=1.0.0        # 兼容 DeepSeek / Qianwen / Ollama / OpenAI（OpenAI-compat 协议）
anthropic>=0.40.0    # 可选，仅 SYNTHESIS_BACKEND=claude 时需要
```

`sentence-transformers` 已在 requirements.txt，CrossEncoder 无需新增依赖。

---

## 实现顺序

| 步骤 | 文件 | 说明 |
|------|------|------|
| 1 | `src/core/config.py` | 增加 LLM/Reranker 常量 |
| 2 | `src/core/reranker.py` | 新建重排器 |
| 3 | `src/core/rag_engine.py` | 新增 `search_with_rerank()`，text BM25 |
| 4 | `src/server/synthesis.py` | 新建多 Provider 合成器 |
| 5 | `src/server/ui.py` | 新增 `/api/answer` 路由 |
| 6 | `requirements.txt` | 追加 `openai` |
| 7 | `webui/src/stores/chat.js` | 新增 `answer()` action |
| 8 | `webui/src/components/InputBar.vue` | 新增按钮 |
| 9 | `webui/src/components/MessageBubble.vue` | 混合布局 |
| 10 | `webui/src/components/SearchResult.vue` | 分组 + 高亮 + 过滤 |
| 11 | — | `cd webui && npm run build` |
| 12 | — | 重启服务器验证 |

---

## 验证方案

```bash
# 1. 配置环境变量
export SYNTHESIS_BACKEND=deepseek
export LLM_API_KEY=sk-xxx

# 2. 安装新依赖
pip install openai>=1.0.0

# 3. 重启服务
python src/server/serve.py

# 4. 接口测试（期望看到 SSE 流）
curl -X POST http://localhost:8765/api/answer \
  -H "Content-Type: application/json" \
  -d '{"query":"音频初始化流程"}' \
  --no-buffer

# 期望输出：
# data: {"type":"results","data":[...5 reranked chunks...]}
# data: {"type":"delta","text":"根据"}
# data: {"type":"delta","text":"知识库中的..."}
# ...
# data: {"type":"done","provider":"deepseek","model":"deepseek-chat"}

# 5. 浏览器验证（http://localhost:8765/ui）
# - 输入查询 → 点击 "✨ AI 回答"
# - 期望：先出现 chunk 卡片（分组、高亮、来源路径），再看到 LLM 答案逐字流出
# - 原有"知识库"/"精准搜索"按钮仍正常工作（不受影响）
```
