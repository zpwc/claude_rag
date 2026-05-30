<template>
  <div class="layout">
    <Sidebar />
    <div class="main">
      <ChatWindow />
      <InputBar />
    </div>
    <FileDrawer />
  </div>
</template>

<script setup>
import Sidebar from './components/Sidebar.vue'
import ChatWindow from './components/ChatWindow.vue'
import InputBar from './components/InputBar.vue'
import FileDrawer from './components/FileDrawer.vue'
</script>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  font-size: 14px;
  background: #f7f8fa;
  color: #1a1a1a;
  height: 100vh;
  overflow: hidden;
}

.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #fff;
}

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d0d0d0; border-radius: 3px; }
</style>
