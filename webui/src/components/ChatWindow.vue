<template>
  <div class="chat-window" ref="container">
    <div v-if="!store.current?.messages?.length" class="welcome">
      <div class="welcome-icon">📚</div>
      <h2>知识库助手</h2>
      <p>在下方输入问题，点击 <b>知识库</b> 进行语义搜索，<br>或点击 <b>精准搜索</b> 查找确切符号/函数名。</p>
    </div>
    <template v-else>
      <MessageBubble
        v-for="(msg, i) in store.current.messages"
        :key="i"
        :msg="msg"
        @view-file="drawerDoc = $event"
      />
      <div v-if="store.loading" class="bubble-wrap assistant">
        <div class="avatar">🤖</div>
        <div class="bubble loading"><span /><span /><span /></div>
      </div>
    </template>
  </div>
  <FileDrawer :doc-name="drawerDoc" @close="drawerDoc = null" />
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'
import MessageBubble from './MessageBubble.vue'
import FileDrawer from './FileDrawer.vue'

const store = useChatStore()
const container = ref(null)
const drawerDoc = ref(null)

watch(() => store.current?.messages?.length, () => {
  nextTick(() => {
    if (container.value) container.value.scrollTop = container.value.scrollHeight
  })
})
</script>

<style scoped>
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #666;
  text-align: center;
  padding: 40px;
}
.welcome-icon { font-size: 48px; }
.welcome h2 { font-size: 22px; color: #333; }
.welcome p { font-size: 14px; line-height: 1.8; }

.bubble-wrap { display: flex; align-items: flex-start; gap: 10px; padding: 6px 20px; }
.avatar { font-size: 22px; flex-shrink: 0; margin-top: 2px; }
.bubble { padding: 10px 14px; border-radius: 12px; background: #f0f2f5; }

.bubble.loading {
  display: flex; gap: 5px; align-items: center;
}
.bubble.loading span {
  width: 7px; height: 7px; border-radius: 50%;
  background: #aaa; display: inline-block;
  animation: bounce 1.2s infinite;
}
.bubble.loading span:nth-child(2) { animation-delay: 0.2s; }
.bubble.loading span:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); }
  40% { transform: translateY(-6px); }
}
</style>
