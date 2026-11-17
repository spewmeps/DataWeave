<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { executeDocument, getDocuments } from '@/api/client'
import type { DocumentSummary } from '@/types/api'

const emit = defineEmits<{
  create: []
  'open-run': [runId: string]
  'count-change': [count: number]
}>()

const documents = ref<DocumentSummary[]>([])
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const query = ref('')
const lastUpdated = ref<Date | null>(null)
const executingVersionId = ref('')
const actionError = ref('')
let timer: number | undefined
let requestVersion = 0
let alive = true

const visibleDocuments = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return documents.value
  return documents.value.filter((item) => item.filename.toLowerCase().includes(keyword) || item.document_id.toLowerCase().includes(keyword))
})
const runningCount = computed(() => documents.value.filter((item) => ['created', 'queued', 'running'].includes(item.run_status || '')).length)
const finishedCount = computed(() => documents.value.filter((item) => ['awaiting_review', 'published'].includes(item.run_status || '')).length)

const statusText: Record<string, string> = {
  created: '已创建', queued: '排队中', running: '解析中', awaiting_review: '待审核', published: '已发布',
  partially_completed: '部分完成', failed: '失败', cancelled: '已取消', stored: '已上传',
}

function statusClass(item: DocumentSummary) {
  if (['awaiting_review', 'published'].includes(item.run_status || '')) return 'completed'
  if (['created', 'queued', 'running'].includes(item.run_status || '')) return 'running'
  if (['failed', 'cancelled', 'partially_completed'].includes(item.run_status || '')) return 'failed'
  return 'stored'
}

function statusLabel(item: DocumentSummary) {
  return statusText[item.run_status || item.upload_status] || item.run_status || item.upload_status
}

function sizeLabel(size: number) {
  return size < 1024 * 1024 ? `${Math.max(1, Math.round(size / 1024))} KB` : `${(size / 1024 / 1024).toFixed(1)} MB`
}

function dateLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
}

function isRunning(item: DocumentSummary) {
  return ['created', 'queued', 'running'].includes(item.run_status || '')
}

function storageLabel(item: DocumentSummary) {
  const location = item.storage_locations?.[0]
  if (!location) return '未标记'
  if (location.service === 'ragflow') return 'RAGFlow'
  if (location.backend === 'local_filesystem') return 'DataWeave · 本地文件'
  return `DataWeave · ${location.backend}`
}

async function execute(item: DocumentSummary) {
  if (executingVersionId.value || isRunning(item)) return
  executingVersionId.value = item.document_version_id
  actionError.value = ''
  try {
    const created = await executeDocument(item.document_version_id)
    emit('open-run', created.run_id)
  } catch (cause) {
    actionError.value = cause instanceof Error ? cause.message : '解析任务创建失败。'
  } finally {
    executingVersionId.value = ''
    await refresh(true)
  }
}

async function refresh(silent = false) {
  const version = ++requestVersion
  if (silent) refreshing.value = true
  try {
    const data = await getDocuments()
    if (!alive || version !== requestVersion) return
    documents.value = data
    emit('count-change', data.length)
    lastUpdated.value = new Date()
    error.value = ''
  } catch (cause) {
    if (alive && version === requestVersion) error.value = cause instanceof Error ? cause.message : '文档列表读取失败。'
  } finally {
    if (alive && version === requestVersion) {
      loading.value = false
      refreshing.value = false
    }
  }
}

onMounted(() => {
  refresh()
  timer = window.setInterval(() => refresh(true), 1200)
})

onBeforeUnmount(() => {
  alive = false
  requestVersion += 1
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <section class="document-list-page">
    <div class="document-summary-grid">
      <article><span>全部文档</span><strong>{{ documents.length }}</strong><small>已保存的论文版本</small></article>
      <article><span>正在解析</span><strong class="live-number">{{ runningCount }}</strong><small>进度自动刷新</small></article>
      <article><span>解析完成</span><strong>{{ finishedCount }}</strong><small>可查看结果或审核</small></article>
      <article class="refresh-card"><span class="refresh-dot" :class="{ spinning: refreshing }">↻</span><div><strong>LIVE</strong><small>{{ lastUpdated ? `更新于 ${lastUpdated.toLocaleTimeString('zh-CN', { hour12: false })}` : '正在连接' }}</small></div></article>
    </div>

    <div class="stage-card document-table-card">
      <header class="document-toolbar">
        <div><span class="eyebrow">DOCUMENT LIBRARY</span><h2>文档列表</h2><p>集中查看上传记录和自动解析进度。</p></div>
        <div class="document-toolbar-actions"><label><span>⌕</span><input v-model="query" placeholder="搜索文档名称或 ID" /></label><button class="primary-action" type="button" @click="emit('create')">＋ 新增文档</button></div>
      </header>

      <div v-if="error" class="document-inline-error"><span>{{ error }}</span><button type="button" @click="refresh()">重新加载</button></div>
      <div v-if="actionError" class="document-inline-error"><span>{{ actionError }}</span><button type="button" @click="actionError = ''">关闭</button></div>
      <div v-if="loading" class="document-list-state">正在加载文档列表…</div>
      <div v-else-if="!documents.length" class="document-empty">
        <span class="empty-document-icon">▤</span>
        <h3>还没有论文文档</h3>
        <p>上传第一篇论文后，系统会自动解析，并在这里持续显示处理进度。</p>
        <button class="primary-action" type="button" @click="emit('create')">＋ 新增文档</button>
      </div>
      <template v-else>
        <div class="document-table-head"><span>文档</span><span>上传时间</span><span>存储后端</span><span>状态</span><span>解析进度</span><span>操作</span></div>
        <div class="document-table-body">
          <article v-for="item in visibleDocuments" :key="item.document_version_id" class="document-row">
            <div class="document-name-cell"><span class="pdf-file-icon">PDF</span><div><strong>{{ item.filename }}</strong><small>{{ sizeLabel(item.size) }} · {{ item.document_id }}</small></div></div>
            <div class="document-time-cell"><strong>{{ dateLabel(item.uploaded_at) }}</strong><small>模板 v{{ item.template_version || 3 }}</small></div>
            <div><span class="storage-backend-badge" :class="item.storage_locations?.[0]?.service"><i />{{ storageLabel(item) }}</span></div>
            <div><span class="document-status" :class="statusClass(item)"><i />{{ statusLabel(item) }}</span></div>
            <div class="document-progress-cell">
              <div><span>{{ item.current_task || (item.progress >= 100 ? '自动步骤已完成' : item.run_id ? '准备解析' : '等待创建任务') }}</span><strong>{{ item.progress }}%</strong></div>
              <span class="document-progress-track"><i :style="{ width: `${item.progress}%` }" /></span>
              <small v-if="item.total_tasks">{{ item.completed_tasks }} / {{ item.total_tasks }} 个步骤</small>
            </div>
            <div class="document-action-cell">
              <button v-if="item.run_id" class="document-view-action" type="button" @click="emit('open-run', item.run_id)">{{ isRunning(item) ? '查看进度' : '查看结果' }}</button>
              <button v-if="!isRunning(item)" class="document-execute-action" type="button" :disabled="Boolean(executingVersionId)" @click="execute(item)">
                {{ executingVersionId === item.document_version_id ? '正在启动…' : item.run_id ? '↻ 重新执行' : '▶ 开始解析' }}
              </button>
              <span v-else>执行中</span>
            </div>
          </article>
          <div v-if="!visibleDocuments.length" class="document-no-result">没有匹配“{{ query }}”的文档。</div>
        </div>
      </template>
    </div>
  </section>
</template>
