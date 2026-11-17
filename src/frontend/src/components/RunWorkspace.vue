<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import DomainContextWorkspace from '@/components/DomainContextWorkspace.vue'
import ArtifactExplorer from '@/components/ArtifactExplorer.vue'
import JsonViewer from '@/components/JsonViewer.vue'
import { buildDomainContextArtifact, buildDomainContextTask } from '@/data/domainContextDemo'
import { getAgentTrace, getRun, getRunArtifacts, publishRun, retryRun } from '@/api/client'
import { useRunStream } from '@/composables/useRunStream'
import type { AgentTrace, AgentTraceEvent, ArtifactRoot, RunSnapshot, SchemaFieldResult, TaskNode, TaskStatus } from '@/types/api'

const props = defineProps<{ runId: string }>()
const emit = defineEmits<{ reset: []; back: []; retried: [runId: string] }>()

const run = ref<RunSnapshot | null>(null)
const selectedTaskId = ref('receive')
const activeTab = ref<'overview' | 'input' | 'output' | 'files' | 'metrics' | 'raw'>('overview')
const loading = ref(true)
const publishing = ref(false)
const retrying = ref(false)
const retryError = ref('')
const error = ref('')
const agentTrace = ref<AgentTrace | null>(null)
const agentTraceLoading = ref(false)
const agentTraceError = ref('')
const artifactRoots = ref<ArtifactRoot[]>([])
const runIdRef = computed(() => props.runId || null)
let requestVersion = 0
let traceRequestVersion = 0
let alive = true

function flatten(tasks: TaskNode[]): TaskNode[] {
  return tasks.flatMap((task) => [task, ...flatten(task.children)])
}

const displayTasks = computed(() => {
  if (!run.value) return []
  if (run.value.tasks.some((task) => task.id === 'domain_context')) return run.value.tasks
  const tasks = [...run.value.tasks]
  const materializeIndex = tasks.findIndex((task) => task.id === 'materialize')
  tasks.splice(materializeIndex >= 0 ? materializeIndex : tasks.length, 0, buildDomainContextTask(run.value))
  return tasks
})
const flatTasks = computed(() => flatten(displayTasks.value))
const selectedTask = computed(() => flatTasks.value.find((task) => task.id === selectedTaskId.value) || flatTasks.value[0])
const contextArtifact = computed(() => run.value ? buildDomainContextArtifact(run.value) : null)
const pipelineProgress = computed(() => {
  const tasks = flatTasks.value
  return { completed: tasks.filter((task) => ['completed', 'skipped'].includes(task.status)).length, total: tasks.length }
})
const selectedAgentLogId = computed(() => {
  if (selectedTask.value?.executor === 'DeepAgent') return selectedTask.value.id
  if (selectedTask.value?.id === 'extract') return 'schema_supervisor'
  return null
})
const selectedAgentLogUrl = computed(() => (
  run.value && selectedAgentLogId.value
    ? `/api/runs/${run.value.id}/agents/${selectedAgentLogId.value}/logs`
    : ''
))
const finished = computed(() => ['awaiting_review', 'published', 'partially_completed', 'failed', 'cancelled'].includes(run.value?.status || ''))
const canRepeat = computed(() => ['awaiting_review', 'published', 'partially_completed', 'failed', 'cancelled'].includes(run.value?.status || ''))
const failureReason = computed(() => {
  if (!run.value || run.value.status !== 'failed') return ''
  const failedTask = flatten(run.value.tasks).find((task) => task.status === 'failed')
  const outputError = failedTask?.output.error
  return typeof outputError === 'string' ? outputError : failedTask?.warnings[0] || '解析流程执行失败。'
})
const schemaFields = computed<SchemaFieldResult[]>(() => {
  if (selectedTask.value?.id !== 'extract') return []
  const fields = selectedTask.value.output.fields
  return Array.isArray(fields) ? fields as unknown as SchemaFieldResult[] : []
})
const agentResultFields = computed(() => agentTrace.value?.result.fields || [])
const summaryOutput = computed(() => Object.entries(selectedTask.value?.output || {}).filter(([key]) => !['fields', 'terms'].includes(key)))
const resolvedTaskInput = computed(() => {
  const task = selectedTask.value
  if (!task || !run.value) return {}
  const upstreamByTask: Record<string, string[]> = {
    parse: ['receive'], parser_submit: ['receive'], parser_wait: ['parser_submit'], parser_persist: ['parser_wait'],
    document_json: ['parse'], extract: ['document_json'], schema_metadata: ['document_json'],
    schema_research: ['document_json'], schema_method: ['document_json'], schema_experiment: ['document_json'],
    schema_merge: ['schema_metadata', 'schema_research', 'schema_method', 'schema_experiment'],
    materialize: ['document_json'], page_index: ['document_json'], graph: ['document_json'], tree: ['document_json'],
    hybrid_retrieval: ['document_json'], validate: ['extract', 'materialize'], publish: ['validate'],
  }
  const upstream = (upstreamByTask[task.id] || []).map((id) => flatTasks.value.find((item) => item.id === id)).filter(Boolean)
  return {
    run: { id: run.value.id, document_id: run.value.document_id, document_version_id: run.value.document_version_id },
    parameters: task.input,
    upstream: Object.fromEntries(upstream.map((item) => [item!.id, item!.output])),
  }
})
const statusText: Record<string, string> = {
  pending: '等待中', queued: '排队中', running: '执行中', completed: '已完成', failed: '失败', retrying: '重试中', skipped: '已跳过', cancelled: '已取消',
  created: '已创建', awaiting_review: '等待审核', published: '已发布', partially_completed: '部分完成',
}

async function refresh() {
  const version = ++requestVersion
  try {
    const snapshot = await getRun(props.runId)
    if (!alive || version !== requestVersion) return
    run.value = snapshot
    error.value = ''
    if (selectedTask.value?.status === 'pending') {
      const runningTask = flatten(snapshot.tasks).find((task) => task.status === 'running')
      if (runningTask) selectedTaskId.value = runningTask.id
    }
    if (selectedAgentLogId.value) void refreshAgentTrace(false)
    if (!artifactRoots.value.length || ['awaiting_review', 'published', 'partially_completed', 'failed', 'cancelled'].includes(snapshot.status)) {
      void refreshArtifacts()
    }
  } catch (cause) {
    if (alive && version === requestVersion) error.value = cause instanceof Error ? cause.message : '无法读取运行状态。'
  } finally {
    if (alive && version === requestVersion) loading.value = false
  }
}

async function refreshArtifacts() {
  try {
    artifactRoots.value = (await getRunArtifacts(props.runId)).roots
  } catch {
    artifactRoots.value = []
  }
}

async function refreshAgentTrace(showLoading = true) {
  const agentId = selectedAgentLogId.value
  if (!agentId || !run.value) {
    agentTrace.value = null
    agentTraceError.value = ''
    return
  }
  const version = ++traceRequestVersion
  if (showLoading) agentTraceLoading.value = true
  try {
    const trace = await getAgentTrace(run.value.id, agentId)
    if (!alive || version !== traceRequestVersion || selectedAgentLogId.value !== agentId) return
    agentTrace.value = trace
    agentTraceError.value = ''
  } catch (cause) {
    if (!alive || version !== traceRequestVersion) return
    agentTrace.value = null
    agentTraceError.value = cause instanceof Error ? cause.message : '无法读取 Agent 执行过程。'
  } finally {
    if (alive && version === traceRequestVersion) agentTraceLoading.value = false
  }
}

const { connectionState, stop: stopStream } = useRunStream(runIdRef, refresh)

function taskIcon(status: TaskStatus) {
  if (status === 'completed') return '✓'
  if (status === 'running') return '↻'
  if (status === 'failed') return '!'
  if (status === 'skipped') return '—'
  return '·'
}

function selectTask(task: TaskNode) {
  selectedTaskId.value = task.id
  activeTab.value = 'overview'
}

function traceEventTitle(event: AgentTraceEvent) {
  const titles: Record<string, string> = {
    'agent.started': 'Agent 开始执行',
    'agent.completed': 'Agent 执行完成',
    'agent.failed': 'Agent 执行失败',
    'supervisor.started': 'Supervisor 开始调度',
    'supervisor.completed': 'Supervisor 合并完成',
    'supervisor.failed': 'Supervisor 执行失败',
    'model.started': '发起模型调用',
    'model.completed': '模型调用完成',
    'model.failed': '模型调用失败',
    'tool.started': '调用工具',
    'tool.completed': '工具返回结果',
    'tool.failed': '工具调用失败',
    'task.started': '任务开始',
    'task.completed': '任务完成',
    'task.failed': '任务失败',
    'orchestrator.state': '主流程同步状态',
    'history.summary': '历史执行摘要',
  }
  return titles[event.event] || event.event
}

function traceEventState(event: AgentTraceEvent) {
  if (event.level === 'ERROR' || event.event.endsWith('.failed')) return 'failed'
  if (event.event.endsWith('.completed')) return 'completed'
  if (event.event.endsWith('.started')) return 'running'
  return 'neutral'
}

function traceEventMeta(event: AgentTraceEvent) {
  const payload = event.payload || {}
  const parts: string[] = []
  if (typeof payload.tool === 'string') parts.push(payload.tool)
  if (typeof payload.model === 'string') parts.push(payload.model)
  if (typeof payload.duration_ms === 'number') parts.push(payload.duration_ms < 1000 ? `${payload.duration_ms} ms` : `${(payload.duration_ms / 1000).toFixed(2)} s`)
  if (typeof payload.input_chars === 'number') parts.push(`输入 ${payload.input_chars} 字符`)
  const usage = payload.token_usage
  if (usage && typeof usage === 'object') {
    const tokenRecord = usage as Record<string, unknown>
    const total = tokenRecord.total_tokens ?? tokenRecord.total_token_count
    if (typeof total === 'number') parts.push(`${total} tokens`)
  }
  if (payload.restored === true) parts.push('由任务快照恢复')
  return parts.join(' · ')
}

function duration(task: TaskNode) {
  if (task.duration_ms == null) return '—'
  return task.duration_ms < 1000 ? `${task.duration_ms} ms` : `${(task.duration_ms / 1000).toFixed(2)} s`
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleTimeString('zh-CN', { hour12: false }) : '—'
}

function isArtifactUrl(value: unknown): value is string {
  return typeof value === 'string' && value.startsWith('/api/')
}

function displayValue(value: unknown) {
  if (value == null || value === '') return '未提取'
  if (Array.isArray(value)) return value.length ? value.map((item) => typeof item === 'string' ? item : JSON.stringify(item)).join('；') : '未提取'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

async function publish() {
  if (!run.value || publishing.value) return
  publishing.value = true
  try {
    run.value = await publishRun(run.value.id)
    selectedTaskId.value = 'publish'
  } finally {
    publishing.value = false
  }
}

async function retry() {
  if (!run.value || retrying.value) return
  retrying.value = true
  retryError.value = ''
  try {
    const created = await retryRun(run.value.id)
    emit('retried', created.run_id)
  } catch (cause) {
    retryError.value = cause instanceof Error ? cause.message : '重新解析任务创建失败。'
  } finally {
    retrying.value = false
  }
}

watch(() => props.runId, () => {
  selectedTaskId.value = 'receive'
  activeTab.value = 'overview'
  retryError.value = ''
  loading.value = true
  artifactRoots.value = []
  refresh()
}, { immediate: true })
watch(selectedAgentLogId, () => {
  agentTrace.value = null
  agentTraceError.value = ''
  void refreshAgentTrace(true)
})
watch(finished, (isFinished) => {
  if (isFinished) { stopStream(); void refreshArtifacts() }
})
onBeforeUnmount(() => { alive = false; requestVersion += 1; traceRequestVersion += 1 })
</script>

<template>
  <section class="run-page">
    <div v-if="loading" class="center-state">正在加载运行…</div>
    <div v-else-if="error" class="center-state error-state"><strong>运行状态读取失败</strong><span>{{ error }}</span><button class="secondary-action" @click="refresh">重试</button></div>
    <template v-else-if="run">
      <header class="run-header">
        <div>
          <span class="eyebrow">INGESTION RUN · {{ run.id }}<template v-if="run.retry_number"> · RETRY {{ run.retry_number }}</template></span>
          <h2>{{ run.document_name }}</h2>
          <p>文档解析、统一 Document JSON、Schema 字段映射、领域上下文提取与知识产物物化过程</p>
          <span class="storage-backend-badge run-storage"><i />{{ run.storage_locations?.[0]?.service === 'ragflow' ? 'RAGFlow' : 'DataWeave · SQLite' }}</span>
        </div>
        <div class="run-header-actions">
          <button class="secondary-action" type="button" @click="emit('back')">← 返回文档列表</button>
          <a class="secondary-action run-log-action" :href="`/api/runs/${run.id}/logs`" target="_blank" rel="noreferrer">查看日志 ↗</a>
          <span class="live-badge" :class="connectionState"><i />{{ connectionState === 'live' && !finished ? 'LIVE' : connectionState === 'polling' ? '轮询中' : statusText[run.status] || run.status }}</span>
          <button v-if="canRepeat" class="primary-action retry-action" type="button" :disabled="retrying" @click="retry">{{ retrying ? '正在重新创建…' : '↻ 重新执行' }}</button>
          <button v-if="run.status === 'awaiting_review'" class="primary-action" :disabled="publishing" @click="publish">{{ publishing ? '发布中…' : '审核并发布' }}</button>
          <button v-if="run.status === 'published'" class="secondary-action" @click="emit('reset')">处理另一篇论文</button>
        </div>
      </header>

      <div class="run-summary">
        <div class="summary-copy"><strong>{{ statusText[run.status] || run.status }}</strong><span>{{ run.progress.current_task || (run.status === 'awaiting_review' ? '所有自动步骤已完成' : '运行已结束') }}</span></div>
        <div class="summary-numbers"><strong>{{ run.progress.percent }}%</strong><span>{{ run.progress.completed }} / {{ run.progress.total }} 个节点</span></div>
        <div class="summary-track"><i :style="{ width: `${run.progress.percent}%` }" /></div>
      </div>

      <div v-if="run.status === 'failed' || run.status === 'cancelled'" class="run-failure-banner">
        <span class="failure-symbol">!</span>
        <div><strong>本次解析未完成</strong><p>{{ failureReason }}</p><small>重新解析会基于同一原始文档和模板创建新的运行记录，本次失败记录会保留。</small></div>
        <button class="secondary-action" type="button" :disabled="retrying" @click="retry">{{ retrying ? '正在创建…' : '重新解析' }}</button>
      </div>
      <div v-if="retryError" class="run-retry-error">{{ retryError }}</div>

      <div class="run-workspace">
        <aside class="pipeline-panel">
          <div class="panel-heading"><div><span class="eyebrow">EXECUTION FLOW</span><h3>解析过程</h3></div><span>{{ pipelineProgress.completed }}/{{ pipelineProgress.total }}</span></div>
          <div class="pipeline-list">
            <div v-for="(task, index) in displayTasks" :key="task.id" class="task-group" :class="task.status">
              <button class="task-row" :class="{ selected: selectedTaskId === task.id }" @click="selectTask(task)">
                <span class="task-state">{{ taskIcon(task.status) }}</span>
                <span class="task-copy"><strong>{{ task.name }}</strong><small>{{ statusText[task.status] }}<template v-if="task.duration_ms"> · {{ duration(task) }}</template></small></span>
                <span class="task-number">{{ String(index + 1).padStart(2, '0') }}</span>
              </button>
              <div v-if="task.children.length" class="child-list">
                <button v-for="child in task.children" :key="child.id" :class="{ selected: selectedTaskId === child.id }" @click="selectTask(child)">
                  <i :class="child.status" />
                  <span><strong>{{ child.name }}</strong><small>{{ statusText[child.status] }}</small></span>
                  <em>{{ duration(child) }}</em>
                </button>
              </div>
            </div>
          </div>
        </aside>

        <main v-if="selectedTask" class="task-detail">
          <header class="task-detail-head">
            <div class="task-title">
              <span class="task-title-icon" :class="selectedTask.status">{{ taskIcon(selectedTask.status) }}</span>
              <div><span class="eyebrow">{{ selectedTask.kind }} · {{ selectedTask.executor }}</span><h3>{{ selectedTask.name }}</h3><p>{{ selectedTask.description }}</p></div>
            </div>
            <div class="task-head-actions">
              <a v-if="selectedAgentLogUrl" class="agent-log-action" :href="selectedAgentLogUrl" target="_blank" rel="noreferrer">查看 Agent 日志 ↗</a>
              <span class="status-chip" :class="selectedTask.status">{{ statusText[selectedTask.status] }}</span>
            </div>
          </header>

          <nav class="detail-tabs">
            <button v-for="tab in (['overview', 'input', 'output', 'files', 'metrics', 'raw'] as const)" :key="tab" :class="{ active: activeTab === tab }" @click="activeTab = tab">
              {{ { overview: '概览', input: '输入', output: '输出', files: '文件', metrics: '指标', raw: '原始数据' }[tab] }}
            </button>
          </nav>

          <div class="detail-content">
            <template v-if="activeTab === 'overview'">
              <div class="metric-cards">
                <article><span>状态</span><strong>{{ statusText[selectedTask.status] }}</strong></article>
                <article><span>执行耗时</span><strong>{{ duration(selectedTask) }}</strong></article>
                <article><span>尝试次数</span><strong>{{ selectedTask.attempt }} / {{ selectedTask.max_attempts }}</strong></article>
                <article><span>执行组件</span><strong>{{ selectedTask.executor }}</strong></article>
              </div>
              <section class="detail-section"><div class="section-head"><h4>执行时间</h4><span>服务器时间</span></div><div class="time-grid"><label><span>开始</span><strong>{{ formatTime(selectedTask.started_at) }}</strong></label><label><span>完成</span><strong>{{ formatTime(selectedTask.finished_at) }}</strong></label></div></section>
              <section v-if="selectedAgentLogId" class="detail-section agent-log-section">
                <div class="section-head"><h4>Agent 执行日志</h4><span>JSONL · APPEND ONLY</span></div>
                <div><code>src/.data/logs/runs/{{ run.id }}/agents/{{ selectedAgentLogId }}.jsonl</code><a :href="selectedAgentLogUrl" target="_blank" rel="noreferrer">打开日志 ↗</a></div>
                <p>记录模型与工具调用、Token、耗时和异常；不记录论文全文、完整 Prompt 或密钥。</p>
              </section>
              <section v-if="selectedAgentLogId" class="detail-section agent-trace-section">
                <div class="section-head">
                  <h4>执行过程</h4>
                  <span v-if="agentTrace">{{ agentTrace.events.length }} 个事件<template v-if="!agentTrace.detailed_trace_available"> · 历史摘要</template></span>
                </div>
                <div v-if="agentTraceLoading && !agentTrace" class="agent-trace-empty">正在读取 Agent 执行过程…</div>
                <div v-else-if="agentTraceError" class="agent-trace-empty failed"><span>{{ agentTraceError }}</span><button @click="refreshAgentTrace(true)">重试</button></div>
                <div v-else-if="agentTrace?.events.length" class="agent-trace-list">
                  <article v-for="(event, index) in agentTrace.events" :key="`${event.timestamp}-${event.event}-${index}`" :class="traceEventState(event)">
                    <i />
                    <div>
                      <header><strong>{{ traceEventTitle(event) }}</strong><time>{{ formatTime(event.timestamp) }}</time></header>
                      <p v-if="event.message">{{ event.message }}</p>
                      <code v-if="traceEventMeta(event)">{{ traceEventMeta(event) }}</code>
                      <details v-if="event.exception"><summary>查看异常堆栈</summary><pre>{{ event.exception }}</pre></details>
                    </div>
                  </article>
                </div>
                <div v-else class="agent-trace-empty">Agent 开始执行后，这里会实时显示模型调用和工具调用。</div>
              </section>
              <section v-if="selectedTask.executor === 'DeepAgent'" class="schema-result-section agent-result-section">
                <div class="section-head">
                  <h4>执行结果</h4>
                  <span v-if="agentTrace">{{ agentTrace.result.extracted }} 已提取 · {{ agentTrace.result.missing }} 缺失 · {{ agentTrace.result.invalid }} 无效</span>
                </div>
                <div v-if="agentResultFields.length" class="schema-field-list">
                  <article v-for="field in agentResultFields" :key="field.key" class="schema-field-card" :class="field.status">
                    <header><div><strong>{{ field.label }}</strong><code>{{ field.key }}</code></div><span>{{ field.status === 'extracted' ? `${Math.round(field.confidence * 100)}%` : field.status === 'missing' ? '未找到' : '需检查' }}</span></header>
                    <pre>{{ displayValue(field.value) }}</pre>
                    <details v-if="field.evidence?.length"><summary>查看原文证据 · {{ field.evidence.length }} 条</summary><blockquote v-for="(evidence, index) in field.evidence" :key="index"><span>第 {{ (evidence.page_idx ?? 0) + 1 }} 页<template v-if="evidence.section"> · {{ evidence.section }}</template></span><p>{{ evidence.quote }}</p></blockquote></details>
                    <div v-else class="no-evidence">暂无可验证的原文证据</div>
                  </article>
                </div>
                <div v-else class="agent-trace-empty">{{ selectedTask.status === 'running' ? 'Agent 正在抽取字段，完成后将在这里显示结果。' : '该 Agent 暂无可展示的字段结果。' }}</div>
              </section>
              <section v-if="selectedTask.id === 'extract' && schemaFields.length" class="schema-result-section">
                <div class="section-head"><h4>字段映射结果</h4><span>{{ schemaFields.filter((field) => field.status === 'extracted').length }} / {{ schemaFields.length }} 已提取</span></div>
                <div class="schema-field-list">
                  <article v-for="field in schemaFields" :key="field.key" class="schema-field-card" :class="field.status">
                    <header><div><strong>{{ field.label }}</strong><code>{{ field.key }}</code></div><span>{{ field.status === 'extracted' ? `${Math.round(field.confidence * 100)}%` : field.status === 'missing' ? '未找到' : '需检查' }}</span></header>
                    <pre>{{ displayValue(field.value) }}</pre>
                    <details v-if="field.evidence?.length"><summary>查看原文证据 · {{ field.evidence.length }} 条</summary><blockquote v-for="(evidence, index) in field.evidence" :key="index"><span>第 {{ (evidence.page_idx ?? 0) + 1 }} 页<template v-if="evidence.section"> · {{ evidence.section }}</template></span><p>{{ evidence.quote }}</p></blockquote></details>
                    <div v-else class="no-evidence">暂无可验证的原文证据</div>
                  </article>
                </div>
              </section>
              <section v-if="selectedTask.id === 'domain_context' && contextArtifact" class="context-run-section">
                <div class="section-head"><h4>领域上下文候选</h4><span>DOCUMENT SCOPE · UI PREVIEW CONTRACT</span></div>
                <p class="context-run-intro">候选来自论文内专有名词、作者命名方法和缩写。运行达到等待审核后，可以查看原文并模拟接受、修改或排除；真实审核写入将在 Context Review API 接入后启用。</p>
                <DomainContextWorkspace :artifact="contextArtifact" compact :readonly="run.status !== 'awaiting_review'" />
              </section>
              <section class="detail-section"><div class="section-head"><h4>处理摘要</h4><span>任务输出</span></div><div v-if="summaryOutput.length" class="output-grid"><label v-for="([key, value]) in summaryOutput" :key="key"><span>{{ key }}</span><a v-if="isArtifactUrl(value)" :href="value" target="_blank" rel="noreferrer">打开结果文件 ↗</a><strong v-else>{{ displayValue(value) }}</strong></label></div><div v-else class="empty-output">任务完成后将在这里展示输出摘要。</div></section>
            </template>

            <template v-else-if="activeTab === 'input' || activeTab === 'output'">
              <section class="json-section"><div class="section-head"><h4>{{ activeTab === 'input' ? '任务输入' : '任务输出' }}</h4><span>{{ Object.keys(activeTab === 'input' ? resolvedTaskInput : selectedTask.output).length }} 个字段</span></div><JsonViewer :value="activeTab === 'input' ? resolvedTaskInput : selectedTask.output" :filename="`${selectedTask.id}-${activeTab}.json`" /></section>
              <section v-if="activeTab === 'output'" class="detail-section artifact-output-section"><div class="section-head"><h4>输出文件与目录</h4><span>ARTIFACT REGISTRY</span></div><ArtifactExplorer :roots="artifactRoots" :task-id="selectedTask.id" /></section>
            </template>

            <template v-else-if="activeTab === 'files'">
              <ArtifactExplorer :roots="artifactRoots" :task-id="selectedTask.id" />
            </template>

            <template v-else-if="activeTab === 'metrics'">
              <div v-if="selectedTask.metrics.length" class="metric-list"><article v-for="metric in selectedTask.metrics" :key="metric.name"><span>{{ metric.label }}</span><strong>{{ metric.value }}<small>{{ metric.unit }}</small></strong><code>{{ metric.name }}</code></article></div>
              <div v-else class="empty-output large">任务执行后将在这里展示页数、Chunk、Token、证据覆盖等过程指标。</div>
            </template>

            <template v-else>
              <section class="json-section"><div class="section-head"><h4>Task Snapshot</h4><span>READ ONLY</span></div><JsonViewer :value="selectedTask" :filename="`${selectedTask.id}-snapshot.json`" /></section>
            </template>
          </div>
        </main>
      </div>
    </template>
  </section>
</template>

