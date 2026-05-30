<template>
  <div class="input-bar">
    <div class="input-wrap">
      <textarea
        ref="ta"
        v-model="query"
        placeholder="发送消息..."
        rows="1"
        @keydown.enter.exact.prevent="submit('answer')"
        @input="autoResize"
      />
    </div>
    <div class="actions">
      <button class="btn exact" :disabled="!query.trim() || store.loading" @click="submit('exact')">
        🔍 精准搜索
      </button>
      <button class="btn semantic" :disabled="!query.trim() || store.loading" @click="submit('all')">
        📚 知识库
      </button>
      <button class="btn answer" :disabled="!query.trim() || store.loading" @click="submit('answer')">
        ✨ AI 回答
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useChatStore } from '../stores/chat'

const store = useChatStore()
const query = ref('')
const ta = ref(null)

function autoResize() {
  if (!ta.value) return
  ta.value.style.height = 'auto'
  ta.value.style.height = Math.min(ta.value.scrollHeight, 120) + 'px'
}

async function submit(mode) {
  const q = query.value.trim()
  if (!q || store.loading) return
  query.value = ''
  if (ta.value) ta.value.style.height = 'auto'
  if (mode === 'answer') {
    await store.answer(q)
  } else {
    await store.search(q, mode)
  }
}
</script>

<style scoped>
.input-bar {
  padding: 12px 20px 16px;
  border-top: 1px solid #e4e6ea;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-wrap {
  border: 1px solid #d0d0d0;
  border-radius: 10px;
  overflow: hidden;
  background: #fafafa;
  transition: border-color 0.15s;
}
.input-wrap:focus-within { border-color: #3b82f6; }

textarea {
  width: 100%;
  padding: 10px 14px;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  font-family: inherit;
  resize: none;
  line-height: 1.5;
  max-height: 120px;
  overflow-y: auto;
}

.actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.btn {
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  border: none;
  font-family: inherit;
  transition: opacity 0.15s, background 0.15s;
}
.btn:disabled { opacity: 0.4; cursor: not-allowed; }

.exact { background: #f0f2f5; color: #333; }
.exact:not(:disabled):hover { background: #e4e6ea; }

.semantic { background: #3b82f6; color: #fff; }
.semantic:not(:disabled):hover { background: #2563eb; }

.answer { background: #7c3aed; color: #fff; }
.answer:not(:disabled):hover { background: #6d28d9; }
</style>
