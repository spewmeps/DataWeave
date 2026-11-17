<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppSidebar from '@/components/AppSidebar.vue'
import DocumentList from '@/components/DocumentList.vue'
import KnowledgeArtifacts from '@/components/KnowledgeArtifacts.vue'
import RunWorkspace from '@/components/RunWorkspace.vue'
import StorageBackendSettings from '@/components/StorageBackendSettings.vue'
import TemplateStep from '@/components/TemplateStep.vue'
import UploadStep from '@/components/UploadStep.vue'
import { createRun, getDefaultTemplate } from '@/api/client'
import type { PaperTemplate, UploadRecord } from '@/types/api'

const activeModule = ref('documents')
const documentView = ref<'list' | 'create' | 'run'>('list')
const documentCount = ref(0)
const upload = ref<UploadRecord | null>(null)
const template = ref<PaperTemplate | null>(null)
const defaultTemplate = ref<PaperTemplate | null>(null)
const runId = ref('')
const loadingTemplate = ref(true)
const creatingRun = ref(false)
const savingTemplate = ref(false)
const templateSaved = ref(false)
const templateCount = ref(1)
const configuredElements = ref<string[]>([])
const storageTargets = ref(['page_index', 'graph', 'tree', 'hybrid_retrieval'])
const error = ref('')

const storageTargetOptions = [
  { id: 'page_index', name: 'PageIndex', backend: 'Document Store' },
  { id: 'graph', name: 'Graph', backend: 'Graph Database' },
  { id: 'tree', name: 'Tree', backend: 'Hierarchy Store' },
  { id: 'hybrid_retrieval', name: 'Retrieval Enhancement', backend: 'DataWeave + RAGFlow' },
]

const pageTitle = computed(() => {
  const labels: Record<string, string> = {
    documents: documentView.value === 'run' ? '解析运行' : documentView.value === 'create' ? '新增文档' : '论文文档',
    templates: '提取模板',
    runs: '解析运行',
    artifacts: '知识产物',
    retrieval: '检索测试',
    settings: '存储后端配置',
  }
  return labels[activeModule.value] || '论文入库'
})

onMounted(async () => {
  try {
    defaultTemplate.value = await getDefaultTemplate()
    template.value = defaultTemplate.value
    configuredElements.value = template.value.elements.filter((item) => item.enabled).map((item) => item.key)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '模板加载失败。'
  } finally {
    loadingTemplate.value = false
  }
})

async function handleUpload(record: UploadRecord) {
  upload.value = record
  if (!upload.value || !template.value) return
  creatingRun.value = true
  error.value = ''
  try {
    const enabledElements = configuredElements.value.length
      ? configuredElements.value
      : template.value.elements.filter((item) => item.enabled).map((item) => item.key)
    const created = await createRun({ upload: upload.value, template: template.value, enabledElements, storageTargets: storageTargets.value })
    runId.value = created.run_id
    documentView.value = 'list'
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '创建解析运行失败。'
  } finally {
    creatingRun.value = false
  }
}

function saveTemplate(payload: { template: PaperTemplate; keys: string[]; storageTargets: string[] }) {
  savingTemplate.value = true
  templateSaved.value = false
  window.setTimeout(() => {
    template.value = payload.template
    configuredElements.value = payload.keys
    storageTargets.value = payload.storageTargets
    savingTemplate.value = false
    templateSaved.value = true
  }, 450)
}

function toggleStorageTarget(id: string) {
  storageTargets.value = storageTargets.value.includes(id)
    ? storageTargets.value.filter((item) => item !== id)
    : [...storageTargets.value, id]
}

function selectModule(id: string) {
  activeModule.value = id
  if (id === 'documents') documentView.value = 'list'
  error.value = ''
}

function newIngestion() {
  reset()
  activeModule.value = 'documents'
  documentView.value = 'create'
}

function openRun(id: string) {
  runId.value = id
  activeModule.value = 'documents'
  documentView.value = 'run'
}

function openRetriedRun(id: string) {
  runId.value = id
  activeModule.value = 'documents'
  documentView.value = 'run'
}

function backToDocuments() {
  runId.value = ''
  activeModule.value = 'documents'
  documentView.value = 'list'
}

function reset() {
  upload.value = null
  runId.value = ''
  error.value = ''
}
</script>

<template>
  <div class="app-shell">
    <AppSidebar :active="activeModule" :document-count="documentCount" :template-count="templateCount" @select="selectModule" />
    <div class="app-main">
      <header class="topbar">
        <div class="breadcrumbs"><span>DataWeave</span><b>›</b><strong>{{ pageTitle }}</strong></div>
        <div class="top-actions"><button class="search-button">⌕ <span>搜索论文、运行或模板</span><kbd>⌘ K</kbd></button><button class="icon-button">◌</button><button v-if="activeModule === 'documents' && documentView === 'create'" class="secondary-action compact" @click="backToDocuments">返回文档列表</button><button v-else class="primary-action compact" @click="newIngestion">＋ 新增文档</button></div>
      </header>

      <main class="page-content">
        <template v-if="activeModule === 'documents'">
          <RunWorkspace v-if="documentView === 'run' && runId" :run-id="runId" @back="backToDocuments" @reset="newIngestion" @retried="openRetriedRun" />
          <template v-else-if="documentView === 'list'">
            <div class="page-heading">
              <div><span class="eyebrow">DOCUMENTS / LIBRARY</span><h1>论文文档</h1><p>统一管理上传文档，并实时跟踪每篇论文的自动解析进度。</p></div>
              <div class="tech-status"><i /><span>Document Registry</span><strong>LIVE</strong></div>
            </div>
            <DocumentList @create="newIngestion" @open-run="openRun" @count-change="documentCount = $event" />
          </template>
          <template v-else>
          <div class="page-heading">
            <div><span class="eyebrow">DOCUMENTS / NEW</span><h1>新增论文文档</h1><p>上传完成后直接进入自动解析，并自动返回文档列表查看进度。</p></div>
            <div class="tech-status"><i /><span>Ingestion Engine</span><strong>READY</strong></div>
          </div>

          <div v-if="error" class="global-error">{{ error }}</div>
          <div v-if="loadingTemplate" class="center-state">正在加载论文模板…</div>
          <div v-else class="ingestion-layout">
            <aside class="ingestion-flow">
              <div class="flow-label">INGESTION FLOW</div>
              <div class="flow-node" :class="{ active: !creatingRun, done: creatingRun }"><span>{{ creatingRun ? '✓' : '01' }}</span><div><strong>文件上传</strong><small>保存论文原始版本</small></div></div>
              <div class="flow-connector"><i /></div>
              <div class="flow-node" :class="{ active: creatingRun }"><span>02</span><div><strong>自动解析</strong><small>解析、抽取与知识编译</small></div></div>
              <div class="flow-note"><b>当前模板</b><span>{{ template?.name }}</span><small>Published v{{ template?.version }} · {{ configuredElements.length }} 个字段</small><button @click="activeModule = 'templates'">配置模板 →</button></div>
            </aside>
            <div class="ingestion-main">
              <div v-if="creatingRun" class="launching-card"><span class="launch-orbit"><i /><i /><i /></span><div><span class="eyebrow">AUTOMATIC PARSING</span><h2>文件已保存，正在创建解析任务</h2><p>{{ upload?.filename }} · 系统即将进入可检查的异步流程。</p></div></div>
              <template v-else>
                <section class="storage-target-config">
                  <div><span class="eyebrow">STORAGE TARGETS</span><h3>存储目标</h3><p>统一 Document JSON 生成后，将按需写入以下后端介质。</p></div>
                  <div class="storage-target-options">
                    <button v-for="item in storageTargetOptions" :key="item.id" type="button" :class="{ active: storageTargets.includes(item.id) }" @click="toggleStorageTarget(item.id)">
                      <span>{{ storageTargets.includes(item.id) ? '✓' : '＋' }}</span><div><strong>{{ item.name }}</strong><small>{{ item.backend }}</small></div>
                    </button>
                  </div>
                </section>
                <UploadStep @completed="handleUpload" />
              </template>
            </div>
          </div>
          </template>
        </template>

        <template v-else-if="activeModule === 'templates'">
          <div class="page-heading"><div><span class="eyebrow">KNOWLEDGE / TEMPLATES</span><h1>提取模板</h1><p>配置需要提取的字段及输出存储；系统内置 Schema 与写入能力保持只读。</p></div><div class="tech-status"><i /><span>Schema Registry</span><strong>ONLINE</strong></div></div>
          <div v-if="loadingTemplate" class="center-state">正在加载论文模板…</div>
          <TemplateStep v-else-if="defaultTemplate && template" :template="defaultTemplate" :active-template-id="template.id" :saving="savingTemplate" :saved="templateSaved" @save="saveTemplate" @count-change="templateCount = $event" />
        </template>

        <template v-else-if="activeModule === 'runs' && runId">
          <RunWorkspace :run-id="runId" @back="backToDocuments" @reset="newIngestion" @retried="openRetriedRun" />
        </template>

        <template v-else-if="activeModule === 'artifacts'">
          <KnowledgeArtifacts @open-run="openRun" @create="newIngestion" />
        </template>

        <template v-else-if="activeModule === 'settings'">
          <StorageBackendSettings />
        </template>

        <section v-else class="module-placeholder"><span>◈</span><h1>{{ pageTitle }}</h1><p>该模块将在后续开发阶段接入。</p><button class="secondary-action" @click="activeModule = 'documents'">返回论文入库</button></section>
      </main>
    </div>
  </div>
</template>

