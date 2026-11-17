<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(defineProps<{ value: unknown; filename?: string }>(), { filename: 'data.json' })
const copied = ref(false)
const content = computed(() => JSON.stringify(props.value ?? null, null, 2))

async function copy() {
  await navigator.clipboard.writeText(content.value)
  copied.value = true
  window.setTimeout(() => { copied.value = false }, 1400)
}

function download() {
  const url = URL.createObjectURL(new Blob([content.value], { type: 'application/json' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = props.filename
  anchor.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="json-viewer">
    <div class="json-viewer-toolbar"><span>JSON · READ ONLY</span><div><button type="button" @click="copy">{{ copied ? '已复制' : '复制' }}</button><button type="button" @click="download">下载</button></div></div>
    <pre><code>{{ content }}</code></pre>
  </div>
</template>
