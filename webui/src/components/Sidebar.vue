<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-icon">📚</span>
      <span class="brand-name">知识库助手</span>
    </div>

    <button class="new-btn" @click="store.newSession()">
      <span>＋</span> 新建对话
    </button>

    <div class="session-list">
      <template v-for="(group, label) in grouped" :key="label">
        <div class="group-label">{{ label }}</div>
        <div
          v-for="s in group"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === store.currentId }"
          @click="store.switchSession(s.id)"
        >
          <span class="session-title">{{ s.title }}</span>
          <button class="del-btn" @click.stop="store.deleteSession(s.id)">×</button>
        </div>
      </template>
    </div>

    <div class="stats" v-if="stats">
      <span>文档 {{ stats.kb_text }} chunks</span>
      <span>代码 {{ stats.kb_code }} chunks</span>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'

const store = useChatStore()
const stats = ref(null)

onMounted(async () => {
  try {
    const r = await fetch('/api/stats')
    stats.value = await r.json()
  } catch (_) {}
})

const grouped = computed(() => {
  const today = new Date(); today.setHours(0,0,0,0)
  const groups = {}
  for (const s of store.sessions) {
    const d = new Date(s.createdAt); d.setHours(0,0,0,0)
    const label = d.getTime() >= today.getTime() ? '今天' : '更早'
    if (!groups[label]) groups[label] = []
    groups[label].push(s)
  }
  return groups
})
</script>

<style scoped>
.sidebar {
  width: 220px;
  min-width: 220px;
  background: #f0f2f5;
  border-right: 1px solid #e4e6ea;
  display: flex;
  flex-direction: column;
  padding: 16px 12px;
  gap: 12px;
  overflow: hidden;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  font-weight: 600;
  font-size: 15px;
  color: #1a1a1a;
}
.brand-icon { font-size: 20px; }

.new-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid #d0d0d0;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #333;
  transition: background 0.15s;
}
.new-btn:hover { background: #e8eaed; }

.session-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-label {
  font-size: 11px;
  color: #888;
  padding: 8px 8px 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.session-item {
  display: flex;
  align-items: center;
  padding: 7px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s;
}
.session-item:hover { background: #e4e6ea; }
.session-item.active { background: #dce0e8; }

.session-title {
  flex: 1;
  font-size: 13px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.del-btn {
  visibility: hidden;
  background: none;
  border: none;
  color: #999;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 0 2px;
}
.session-item:hover .del-btn { visibility: visible; }
.del-btn:hover { color: #e55; }

.stats {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px;
  background: #e8eaed;
  border-radius: 6px;
  font-size: 11px;
  color: #666;
}
</style>
