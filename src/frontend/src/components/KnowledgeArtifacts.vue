<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import DomainContextWorkspace from '@/components/DomainContextWorkspace.vue'
import { getDocuments, getRun } from '@/api/client'
import { buildDomainContextArtifact } from '@/data/domainContextDemo'
import type { DocumentSummary, DomainContextArtifact, RunSnapshot } from '@/types/api'

const emit = defineEmits<{ 'open-run': [runId: string]; create: [] }>()

const documents = ref<DocumentSummary[]>([])
const runs = ref<Record<string, RunSnapshot>>({})
const selectedVersionId = ref('')
const activeArtifact = ref<'overview' | 'page_index' | 'graph' | 'tree' | 'hybrid' | 'domain_context'>('overview')
const loading = ref(true)
const error = ref('')

const availableDocuments = computed(() => documents.value.filter((document) => document.run_id && runs.value[document.run_id]))
const selectedDocument = computed(() => availableDocuments.value.find((document) => document.document_version_id === selectedVersionId.value) || availableDocuments.value[0])
const selectedRun = computed(() => selectedDocument.value?.run_id ? runs.value[selectedDocument.value.run_id] : null)
const contextArtifact = computed<DomainContextArtifact | null>(() => selectedRun.value ? buildDomainContextArtifact(selectedRun.value) : null)
const published = computed(() => selectedRun.value?.status === 'published')

const artifactTabs = [
  { id: 'overview', label: '总览', icon: '◇' },
  { id: 'page_index', label: 'PageIndex', icon: '▤' },
  { id: 'graph', label: 'Graph', icon: '⌘' },
  { id: 'tree', label: 'Tree', icon: '⑂' },
  { id: 'hybrid', label: 'Hybrid Retrieval', icon: '⌕' },
  { id: 'domain_context', label: '领域上下文', icon: 'Aa' },
] as const

const assetCards = computed(() => {
  const run = selectedRun.value
  const context = contextArtifact.value
  return [
    { id: 'page_index', icon: '▤', name: 'PageIndex', backend: 'Document Store', status: 'ready', metric: '19 个章节节点', detail: '章节、页面、表格与证据位置' },
    { id: 'graph', icon: '⌘', name: 'Graph', backend: 'Graph Store', status: 'ready', metric: '24 条关系', detail: '实体、声明与有证据关系' },
    { id: 'tree', icon: '⑂', name: 'Tree', backend: 'Hierarchy Store', status: 'ready', metric: '5 个主题节点', detail: '研究主题与论文归属' },
    { id: 'hybrid', icon: '⌕', name: 'Hybrid Retrieval', backend: 'Search + Vector', status: 'ready', metric: '87 条索引记录', detail: '全文、字段与向量索引' },
    { id: 'domain_context', icon: 'Aa', name: '领域上下文', backend: 'Context Registry', status: published.value ? 'published' : 'review', metric: context ? `${context.terms.length} 个术语 / 方法` : '尚未生成', detail: run ? `${context?.terms.filter((term) => ['review_pending', 'discovered', 'ambiguous'].includes(term.status)).length || 0} 个待处理 · 证据覆盖 ${Math.round((context?.evidence_coverage || 0) * 100)}%` : '等待解析运行' },
  ]
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    documents.value = await getDocuments()
    const runIds = [...new Set(documents.value.map((document) => document.run_id).filter((id): id is string => Boolean(id)))]
    const snapshots = await Promise.all(runIds.map(async (id) => [id, await getRun(id)] as const))
    runs.value = Object.fromEntries(snapshots)
    const first = documents.value.find((document) => document.run_id && runs.value[document.run_id])
    if (first && !selectedVersionId.value) selectedVersionId.value = first.document_version_id
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法读取知识产物。'
  } finally {
    loading.value = false
  }
}

function selectArtifact(id: string) {
  activeArtifact.value = id as typeof activeArtifact.value
}

onMounted(load)
</script>

<template>
  <section class="artifacts-page">
    <div class="page-heading artifacts-heading">
      <div><span class="eyebrow">KNOWLEDGE / ARTIFACTS</span><h1>知识产物</h1><p>查看每篇论文生成的结构、关系、检索索引与领域上下文，并核对其证据和发布状态。</p></div>
      <div class="tech-status"><i /><span>Artifact Registry</span><strong>ONLINE</strong></div>
    </div>

    <div v-if="loading" class="center-state">正在加载知识产物…</div>
    <div v-else-if="error" class="center-state error-state"><strong>知识产物读取失败</strong><span>{{ error }}</span><button class="secondary-action" @click="load">重试</button></div>
    <div v-else-if="!availableDocuments.length" class="artifact-empty-state"><span>⬡</span><h2>还没有可查看的知识产物</h2><p>上传并解析一篇论文后，PageIndex、Graph、Tree、检索索引和领域上下文会显示在这里。</p><button class="primary-action" @click="emit('create')">＋ 新增论文文档</button></div>
    <template v-else-if="selectedDocument && selectedRun">
      <div class="artifact-document-bar">
        <div class="artifact-document-main"><span class="pdf-badge">PDF</span><div><small>当前论文</small><strong>{{ selectedDocument.filename }}</strong><code>{{ selectedDocument.document_version_id }}</code></div></div>
        <label><span>切换论文</span><select v-model="selectedVersionId"><option v-for="document in availableDocuments" :key="document.document_version_id" :value="document.document_version_id">{{ document.filename }}</option></select></label>
        <div class="artifact-release"><span :class="{ published }">{{ published ? '已发布' : '待审核' }}</span><small>{{ published ? 'Artifact Manifest v1' : 'Run-scoped Draft' }}</small></div>
        <button class="secondary-action" @click="selectedDocument.run_id && emit('open-run', selectedDocument.run_id)">查看解析运行 ↗</button>
      </div>

      <div class="artifact-shell">
        <nav class="artifact-tabs">
          <button v-for="tab in artifactTabs" :key="tab.id" :class="{ active: activeArtifact === tab.id }" @click="activeArtifact = tab.id"><span>{{ tab.icon }}</span><strong>{{ tab.label }}</strong><small v-if="tab.id === 'domain_context' && contextArtifact">{{ contextArtifact.terms.length }}</small></button>
        </nav>

        <main class="artifact-content">
          <template v-if="activeArtifact === 'overview'">
            <header class="artifact-section-head"><div><span class="eyebrow">ARTIFACT MANIFEST</span><h2>论文知识产物总览</h2><p>所有产物共享文档版本和证据锚点；领域上下文在审核后形成独立 Release。</p></div><div><strong>{{ assetCards.length }}</strong><span>资产类型</span></div></header>
            <div class="artifact-card-grid">
              <button v-for="card in assetCards" :key="card.id" @click="selectArtifact(card.id)">
                <span class="artifact-card-icon">{{ card.icon }}</span>
                <div><small>{{ card.backend }}</small><h3>{{ card.name }}</h3><p>{{ card.detail }}</p><strong>{{ card.metric }}</strong></div>
                <em :class="card.status">{{ card.status === 'published' ? 'PUBLISHED' : card.status === 'review' ? 'REVIEW' : 'READY' }}</em>
                <b>查看详情 →</b>
              </button>
            </div>
            <section class="artifact-quality-strip"><div><span>证据可定位</span><strong>PASS</strong></div><div><span>Document Schema</span><strong>v1</strong></div><div><span>Context Schema</span><strong>v1-preview</strong></div><div><span>最近活动</span><strong>{{ new Date(selectedRun.last_activity_at).toLocaleString('zh-CN') }}</strong></div></section>
          </template>

          <template v-else-if="activeArtifact === 'domain_context' && contextArtifact">
            <header class="artifact-section-head context-artifact-head"><div><span class="eyebrow">DOMAIN CONTEXT / DOCUMENT SCOPE</span><h2>领域上下文</h2><p>论文专有名词、作者命名方法和缩写。当前仅表示本文中的定义，不推断跨论文等价关系。</p></div><div class="context-release-badge"><span>{{ contextArtifact.status === 'published' ? '已发布' : 'Draft' }}</span><strong>{{ contextArtifact.release_version ? `Context Release v${contextArtifact.release_version}` : '等待审核发布' }}</strong><small>{{ contextArtifact.schema_version }}</small></div></header>
            <div v-if="contextArtifact.status !== 'published'" class="artifact-review-banner"><span>!</span><div><strong>领域上下文仍是运行草稿</strong><p>已审核候选会随文档发布；未审核和歧义候选继续保留在 Draft，不进入正式检索上下文。</p></div><button class="secondary-action" @click="emit('open-run', selectedRun.id)">前往解析运行审核</button></div>
            <DomainContextWorkspace :artifact="contextArtifact" readonly />
          </template>

          <template v-else>
            <header class="artifact-section-head"><div><span class="eyebrow">{{ activeArtifact.toUpperCase() }}</span><h2>{{ artifactTabs.find((tab) => tab.id === activeArtifact)?.label }}</h2><p>该资产已完成物化。当前页面保留审核入口，详细可视化将在对应后端查询接口接入后展示。</p></div></header>
            <div class="artifact-preview-placeholder"><span>{{ artifactTabs.find((tab) => tab.id === activeArtifact)?.icon }}</span><h3>{{ assetCards.find((card) => card.id === activeArtifact)?.metric }}</h3><p>{{ assetCards.find((card) => card.id === activeArtifact)?.detail }}</p><button class="secondary-action" @click="activeArtifact = 'overview'">返回产物总览</button></div>
          </template>
        </main>
      </div>
    </template>
  </section>
</template>
