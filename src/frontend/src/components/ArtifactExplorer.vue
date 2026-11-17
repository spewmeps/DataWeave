<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ArtifactTreeNode from '@/components/ArtifactTreeNode.vue'
import JsonViewer from '@/components/JsonViewer.vue'
import type { ArtifactRoot, ArtifactTreeEntry } from '@/types/api'

const props = defineProps<{ roots: ArtifactRoot[]; taskId: string }>()
const selected = ref<ArtifactTreeEntry | null>(null)
const textContent = ref('')
const jsonContent = ref<unknown>(null)
const loading = ref(false)
const error = ref('')
const visibleRoots = computed(() => props.roots.filter((root) => root.task_ids.includes(props.taskId)))
const isJson = computed(() => selected.value?.mime_type === 'application/json' || selected.value?.name.endsWith('.json'))
const isImage = computed(() => selected.value?.mime_type?.startsWith('image/'))
const isPdf = computed(() => selected.value?.mime_type === 'application/pdf')

async function selectFile(entry: ArtifactTreeEntry) {
  selected.value = entry
  textContent.value = ''
  jsonContent.value = null
  error.value = ''
  if (!entry.content_url || isImage.value || isPdf.value) return
  loading.value = true
  try {
    const response = await fetch(entry.content_url)
    if (!response.ok) throw new Error(`文件读取失败（${response.status}）`)
    const content = await response.text()
    if (isJson.value) {
      try { jsonContent.value = JSON.parse(content) } catch { textContent.value = content }
    } else textContent.value = content
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '文件读取失败。'
  } finally { loading.value = false }
}

watch(() => props.taskId, () => { selected.value = null; textContent.value = ''; jsonContent.value = null; error.value = '' })
</script>

<template>
  <div v-if="visibleRoots.length" class="artifact-explorer">
    <aside class="artifact-tree-panel">
      <section v-for="root in visibleRoots" :key="root.id">
        <header><span>📦</span><div><strong>{{ root.label }}</strong><small>{{ root.description }}</small></div></header>
        <ArtifactTreeNode v-for="entry in root.entries" :key="`${root.id}:${entry.path}`" :entry="entry" :selected-path="selected?.path" @select="selectFile" />
      </section>
    </aside>
    <main class="artifact-preview">
      <div v-if="!selected" class="artifact-preview-empty"><span>⌘</span><strong>选择文件查看内容</strong><p>目录来自后端受控产物根，不暴露任意服务器路径。</p></div>
      <template v-else>
        <header><div><strong>{{ selected.name }}</strong><code>{{ selected.path }}</code></div><a v-if="selected.download_url" :href="selected.download_url">下载文件 ↓</a></header>
        <div v-if="loading" class="artifact-preview-empty">正在读取文件…</div>
        <div v-else-if="error" class="artifact-preview-empty failed">{{ error }}</div>
        <JsonViewer v-else-if="jsonContent !== null" :value="jsonContent" :filename="selected.name" />
        <img v-else-if="isImage && selected.content_url" :src="selected.content_url" :alt="selected.name" />
        <iframe v-else-if="isPdf && selected.content_url" :src="selected.content_url" :title="selected.name" />
        <pre v-else><code>{{ textContent }}</code></pre>
      </template>
    </main>
  </div>
  <div v-else class="empty-output large">该步骤暂时没有已登记的输入或输出文件。运行产生文件后会自动映射到这里。</div>
</template>
