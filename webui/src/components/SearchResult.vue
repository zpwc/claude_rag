<template>
  <div class="results">
    <div class="summary">
      找到 {{ results.length }} 条相关结果
      <span v-if="hasRerank">（已重排）</span>
    </div>

    <div v-for="group in grouped" :key="group.docName" class="group">
      <div class="group-header">
        <span class="group-name">{{ group.docName }}</span>
        <span class="group-count">{{ group.chunks.length }} chunk{{ group.chunks.length > 1 ? 's' : '' }}</span>
        <button class="view-btn" @click="$emit('view-file', group.docName)">查看文件 →</button>
      </div>

      <div
        v-for="(r, ci) in group.chunks"
        :key="ci"
        class="card"
        :class="{ 'low-relevance': isLowRelevance(r) }"
      >
        <div class="card-header">
          <span class="badge" :class="badgeClass(r.file_type)">.{{ r.file_type }}</span>
          <span class="collection">{{ r.collection }}</span>
          <span v-if="r.rerank_score != null" class="score rerank">
            重排 {{ r.rerank_score.toFixed(2) }}
          </span>
          <span v-else-if="r.score != null" class="score">
            {{ (r.score * 100).toFixed(0) }}%
          </span>
          <span v-if="r.total_chunks > 1" class="chunk-info">
            chunk {{ r.chunk_index + 1 }}/{{ r.total_chunks }}
          </span>
          <span v-if="isLowRelevance(r)" class="low-tag">低相关度</span>
          <button class="copy-chunk-btn" @click="copyChunk(r.content, group.docName, ci)">
            {{ copiedKey === expandKey(group.docName, ci) ? '已复制 ✓' : '复制' }}
          </button>
        </div>
        <pre
          class="content"
          :class="{ expanded: expandKey(group.docName, ci) in expanded }"
          v-html="highlighted(r.content, r.file_type)"
        />
        <button class="toggle" @click="toggleExpand(group.docName, ci)">
          {{ expandKey(group.docName, ci) in expanded ? '收起' : '展开' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import hljs from 'highlight.js/lib/core'
import c from 'highlight.js/lib/languages/c'
import cpp from 'highlight.js/lib/languages/cpp'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import go from 'highlight.js/lib/languages/go'
import rust from 'highlight.js/lib/languages/rust'
import shell from 'highlight.js/lib/languages/shell'
import ini from 'highlight.js/lib/languages/ini'
import 'highlight.js/styles/github.css'

hljs.registerLanguage('c', c)
hljs.registerLanguage('cpp', cpp)
hljs.registerLanguage('h', c)
hljs.registerLanguage('py', python)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('go', go)
hljs.registerLanguage('rs', rust)
hljs.registerLanguage('sh', shell)
hljs.registerLanguage('ini', ini)

const EXT_MAP = { c:'c', h:'h', cpp:'cpp', cc:'cpp', py:'py', js:'js', ts:'ts', go:'go', rs:'rs', sh:'sh', ini:'ini' }

const props = defineProps({ results: Array })
defineEmits(['view-file'])

const expanded = reactive({})
const copiedKey = ref(null)

const hasRerank = computed(() => props.results.some(r => r.rerank_score != null))

const grouped = computed(() => {
  const map = new Map()
  for (const r of props.results) {
    const key = r.doc_name || 'unknown'
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(r)
  }
  return Array.from(map.entries()).map(([docName, chunks]) => ({ docName, chunks }))
})

const CODE_EXTS = new Set(['c','h','cpp','py','js','ts','go','rs','java','sh'])

function badgeClass(ext) {
  return CODE_EXTS.has(ext) ? 'badge-code' : 'badge-doc'
}

function isLowRelevance(r) {
  if (r.rerank_score != null) return r.rerank_score < -2
  return (r.score || 0) < 0.3
}

function highlighted(code, fileType) {
  const lang = EXT_MAP[fileType]
  if (lang && hljs.getLanguage(lang)) {
    try { return hljs.highlight(code, { language: lang }).value }
    catch (_) {}
  }
  try { return hljs.highlightAuto(code).value }
  catch (_) { return code }
}

function expandKey(docName, ci) { return `${docName}::${ci}` }

function toggleExpand(docName, ci) {
  const k = expandKey(docName, ci)
  if (k in expanded) delete expanded[k]
  else expanded[k] = true
}

async function copyChunk(content, docName, ci) {
  try {
    await navigator.clipboard.writeText(content)
  } catch {
    const el = document.createElement('textarea')
    el.value = content
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
  }
  const k = expandKey(docName, ci)
  copiedKey.value = k
  setTimeout(() => { copiedKey.value = null }, 2000)
}
</script>

<style scoped>
.results { display: flex; flex-direction: column; gap: 12px; }

.summary { font-size: 13px; color: #555; margin-bottom: 2px; }

.group { display: flex; flex-direction: column; gap: 6px; }

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #eef2ff;
  border-radius: 6px;
  border-left: 3px solid #6366f1;
}

.group-name {
  font-weight: 600;
  font-size: 13px;
  color: #1a1a1a;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-count { font-size: 11px; color: #888; }

.view-btn {
  background: none;
  border: 1px solid #6366f1;
  color: #6366f1;
  border-radius: 5px;
  padding: 2px 8px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.view-btn:hover { background: #eef2ff; }

.card {
  border: 1px solid #e4e6ea;
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;
  margin-left: 12px;
  transition: opacity 0.15s;
}
.card.low-relevance { opacity: 0.5; }

.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #f0f2f5;
  border-bottom: 1px solid #e4e6ea;
  flex-wrap: wrap;
}

.badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  font-weight: 500;
}
.badge-code { background: #dbeafe; color: #1e40af; }
.badge-doc  { background: #dcfce7; color: #166534; }

.collection { font-size: 11px; color: #888; }

.score { font-size: 12px; color: #16a34a; font-weight: 600; }
.score.rerank { color: #7c3aed; }

.chunk-info { font-size: 11px; color: #aaa; }

.low-tag {
  font-size: 11px;
  color: #888;
  background: #f0f0f0;
  border-radius: 4px;
  padding: 1px 5px;
}

.copy-chunk-btn {
  margin-left: auto;
  background: none;
  border: 1px solid #d1d5db;
  color: #555;
  border-radius: 4px;
  padding: 1px 8px;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s;
}
.copy-chunk-btn:hover { background: #f0f0f0; }

.content {
  padding: 10px 12px;
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 80px;
  overflow: hidden;
  color: #333;
  line-height: 1.5;
  transition: max-height 0.2s;
  margin: 0;
}
.content.expanded { max-height: 400px; overflow-y: auto; }

.toggle {
  display: block;
  width: 100%;
  background: none;
  border: none;
  border-top: 1px solid #e4e6ea;
  padding: 5px;
  font-size: 12px;
  color: #888;
  cursor: pointer;
}
.toggle:hover { background: #f0f2f5; }
</style>
