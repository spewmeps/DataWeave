<script setup lang="ts">
import { computed, ref } from 'vue'
import { uploadPdf } from '@/api/client'
import type { UploadRecord } from '@/types/api'

const emit = defineEmits<{ completed: [record: UploadRecord] }>()

const input = ref<HTMLInputElement | null>(null)
const selected = ref<File | null>(null)
const progress = ref(0)
const status = ref<'idle' | 'uploading' | 'stored' | 'failed'>('idle')
const error = ref('')
const dragging = ref(false)

const sizeLabel = computed(() => {
  if (!selected.value) return ''
  return selected.value.size < 1024 * 1024
    ? `${Math.max(1, Math.round(selected.value.size / 1024))} KB`
    : `${(selected.value.size / 1024 / 1024).toFixed(1)} MB`
})

function choose(file?: File) {
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    error.value = '请选择 PDF 文件。'
    return
  }
  selected.value = file
  error.value = ''
  status.value = 'idle'
  progress.value = 0
}

function onDrop(event: DragEvent) {
  dragging.value = false
  choose(event.dataTransfer?.files[0])
}

function useDemoFile() {
  const content = '%PDF-1.7\n% DataWeave demo paper\n1 0 obj << /Type /Catalog >> endobj\n%%EOF'
  choose(new File([content], 'speculative-decoding-demo.pdf', { type: 'application/pdf' }))
}

async function upload() {
  if (!selected.value || status.value === 'uploading') return
  status.value = 'uploading'
  error.value = ''
  try {
    const record = await uploadPdf(selected.value, (value) => (progress.value = value))
    status.value = 'stored'
    emit('completed', record)
  } catch (cause) {
    status.value = 'failed'
    error.value = cause instanceof Error ? cause.message : '上传失败。'
  }
}
</script>

<template>
  <section class="stage-card upload-stage">
    <div class="stage-intro">
      <span class="eyebrow">STEP 1 · DOCUMENT</span>
      <h2>上传一篇论文</h2>
      <p>上传完成后，系统将立即使用当前已发布模板开始自动解析。</p>
    </div>

    <div
      class="drop-zone"
      :class="{ dragging, selected: Boolean(selected) }"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
      @click="input?.click()"
    >
      <input ref="input" type="file" accept="application/pdf,.pdf" hidden @change="choose(($event.target as HTMLInputElement).files?.[0])" />
      <div class="upload-icon">⇧</div>
      <template v-if="selected">
        <strong>{{ selected.name }}</strong>
        <span>{{ sizeLabel }} · PDF</span>
        <small>点击可重新选择</small>
      </template>
      <template v-else>
        <strong>拖入 PDF，或点击选择文件</strong>
        <span>当前 Demo 支持文本型 PDF，最大 50 MB</span>
      </template>
    </div>

    <div v-if="status === 'uploading'" class="upload-progress">
      <div><span>正在上传并校验文件</span><b>{{ progress }}%</b></div>
      <i><span :style="{ width: `${progress}%` }" /></i>
    </div>
    <p v-if="error" class="form-error">{{ error }}</p>

    <div class="stage-actions">
      <button class="secondary-action" type="button" @click="useDemoFile">使用示例论文</button>
      <button class="primary-action" type="button" :disabled="!selected || status === 'uploading'" @click="upload">
        {{ status === 'uploading' ? '上传中…' : '上传并自动解析' }}
      </button>
    </div>
  </section>
</template>

