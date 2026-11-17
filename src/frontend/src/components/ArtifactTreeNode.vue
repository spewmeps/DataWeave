<script setup lang="ts">
import { ref } from 'vue'
import type { ArtifactTreeEntry } from '@/types/api'

defineOptions({ name: 'ArtifactTreeNode' })
defineProps<{ entry: ArtifactTreeEntry; selectedPath?: string }>()
const emit = defineEmits<{ select: [entry: ArtifactTreeEntry] }>()
const expanded = ref(true)

function activate(entry: ArtifactTreeEntry) {
  if (entry.kind === 'directory') expanded.value = !expanded.value
  else emit('select', entry)
}
</script>

<template>
  <div class="artifact-tree-node">
    <button type="button" :class="{ selected: entry.path === selectedPath }" @click="activate(entry)">
      <span>{{ entry.kind === 'directory' ? (expanded ? '▾' : '▸') : '·' }}</span><i>{{ entry.kind === 'directory' ? '📁' : '📄' }}</i><strong>{{ entry.name }}</strong><small v-if="entry.kind === 'file'">{{ entry.size == null ? '' : entry.size < 1024 ? `${entry.size} B` : `${(entry.size / 1024).toFixed(1)} KB` }}</small>
    </button>
    <div v-if="entry.kind === 'directory' && expanded" class="artifact-tree-children">
      <ArtifactTreeNode v-for="child in entry.children" :key="child.path" :entry="child" :selected-path="selectedPath" @select="emit('select', $event)" />
    </div>
  </div>
</template>
