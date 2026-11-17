<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ active: string; documentCount: number; templateCount: number }>()
const emit = defineEmits<{ select: [id: string] }>()

const items = computed(() => [
  { id: 'documents', icon: '▤', label: '论文文档', count: String(props.documentCount) },
  { id: 'templates', icon: '◇', label: '提取模板', count: String(props.templateCount) },
  { id: 'runs', icon: '⌁', label: '解析运行', count: '' },
  { id: 'artifacts', icon: '⬡', label: '知识产物', count: '' },
  { id: 'retrieval', icon: '⌕', label: '检索测试', count: '' },
])
</script>

<template>
  <aside class="app-sidebar">
    <div class="brand">
      <span class="brand-mark"><i /><i /><i /></span>
      <div><strong>DataWeave</strong><small>Paper Intelligence</small></div>
    </div>

    <div class="workspace-card">
      <span>AI</span>
      <div><strong>论文技术洞察</strong><small>Demo Workspace</small></div>
      <b>⌄</b>
    </div>

    <nav>
      <p>WORKSPACE</p>
      <button v-for="item in items" :key="item.id" :class="{ active: active === item.id }" @click="emit('select', item.id)">
        <span class="nav-icon">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
        <small v-if="item.count">{{ item.count }}</small>
      </button>
    </nav>

    <div class="sidebar-footer">
      <button :class="{ active: active === 'settings' }" @click="emit('select', 'settings')"><span class="nav-icon">⚙</span><span>存储后端配置</span></button>
      <div class="profile"><span>LW</span><div><strong>Lin Wei</strong><small>Domain analyst</small></div><b>···</b></div>
    </div>
  </aside>
</template>

