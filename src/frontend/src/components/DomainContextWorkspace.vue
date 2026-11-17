<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { DomainContextArtifact, DomainContextTerm, DomainContextTermStatus, DomainContextTermType } from '@/types/api'

const props = withDefaults(defineProps<{
  artifact: DomainContextArtifact
  compact?: boolean
  readonly?: boolean
}>(), { compact: false, readonly: false })

const search = ref('')
const typeFilter = ref<'all' | DomainContextTermType>('all')
const statusFilter = ref<'all' | DomainContextTermStatus>('all')
const selectedId = ref<string | null>(null)
const localTerms = ref<DomainContextTerm[]>([])
const notice = ref('')

watch(() => props.artifact, (artifact) => {
  localTerms.value = artifact.terms.map((term) => ({
    ...term,
    aliases: [...term.aliases],
    evidence: term.evidence.map((evidence) => ({ ...evidence })),
    related_terms: [...term.related_terms],
  }))
}, { immediate: true, deep: true })

const typeLabels: Record<DomainContextTermType, string> = {
  new_term: '新术语', method: '方法 / 机制', acronym: '缩写', dataset: '数据集', metric: '指标 / 变量',
}
const statusLabels: Record<DomainContextTermStatus, string> = {
  discovered: '已发现', evidence_ready: '证据完整', review_pending: '待审核', ambiguous: '存在歧义', excluded: '已排除', published: '已发布',
}

const filteredTerms = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return localTerms.value.filter((term) => {
    const matchesSearch = !keyword || [term.name, term.surface_form, term.definition, ...term.aliases].some((value) => value.toLowerCase().includes(keyword))
    return matchesSearch && (typeFilter.value === 'all' || term.type === typeFilter.value) && (statusFilter.value === 'all' || term.status === statusFilter.value)
  })
})
const selectedTerm = computed(() => localTerms.value.find((term) => term.id === selectedId.value) || null)
const publishedCount = computed(() => localTerms.value.filter((term) => term.status === 'published').length)
const readyCount = computed(() => localTerms.value.filter((term) => ['evidence_ready', 'published'].includes(term.status)).length)
const reviewCount = computed(() => localTerms.value.filter((term) => ['review_pending', 'discovered'].includes(term.status)).length)
const ambiguousCount = computed(() => localTerms.value.filter((term) => term.status === 'ambiguous').length)

function openTerm(term: DomainContextTerm) {
  selectedId.value = term.id
  notice.value = ''
}

function review(status: 'evidence_ready' | 'excluded') {
  if (!selectedTerm.value || props.readonly) return
  selectedTerm.value.status = status
  selectedTerm.value.review_note = status === 'excluded' ? '已在当前页面排除；接入后端后将写入 Review Record。' : '已在当前页面接受；接入后端后将写入 Review Record。'
  notice.value = status === 'excluded' ? '已将该候选标记为排除。' : '已接受该候选，等待随文档发布。'
}
</script>

<template>
  <section class="context-workspace" :class="{ compact }">
    <div class="context-summary-grid">
      <article><span>发现候选</span><strong>{{ localTerms.length }}</strong><small>论文级作用域</small></article>
      <article><span>证据完整</span><strong>{{ readyCount }}</strong><small>{{ Math.round(artifact.evidence_coverage * 100) }}% 证据覆盖</small></article>
      <article><span>待审核</span><strong>{{ reviewCount }}</strong><small>不会进入正式 Release</small></article>
      <article class="warning"><span>存在歧义</span><strong>{{ ambiguousCount }}</strong><small>需要人工选择作用域</small></article>
      <article v-if="!compact"><span>已发布</span><strong>{{ publishedCount }}</strong><small>{{ artifact.release_version ? `Context Release v${artifact.release_version}` : '当前为 Draft' }}</small></article>
    </div>

    <div class="context-toolbar">
      <label><span>⌕</span><input v-model="search" placeholder="搜索术语、方法或定义" /></label>
      <select v-model="typeFilter"><option value="all">全部类型</option><option v-for="(label, value) in typeLabels" :key="value" :value="value">{{ label }}</option></select>
      <select v-model="statusFilter"><option value="all">全部状态</option><option v-for="(label, value) in statusLabels" :key="value" :value="value">{{ label }}</option></select>
      <span class="context-result-count">{{ filteredTerms.length }} / {{ localTerms.length }}</span>
    </div>

    <div class="context-table-wrap">
      <div class="context-table-head"><span>术语 / 方法</span><span>类型</span><span>本文定义</span><span>证据</span><span>状态</span></div>
      <button v-for="term in filteredTerms" :key="term.id" class="context-table-row" type="button" @click="openTerm(term)">
        <span class="context-term-name"><strong>{{ term.name }}</strong><small>{{ term.surface_form }} · 出现 {{ term.mention_count }} 次</small></span>
        <span><em class="context-type-chip">{{ typeLabels[term.type] }}</em></span>
        <span class="context-definition">{{ term.definition }}</span>
        <span class="context-evidence-count"><b>{{ term.evidence.length }}</b><small>条原文</small></span>
        <span><em class="context-status-chip" :class="term.status">{{ statusLabels[term.status] }}</em></span>
      </button>
      <div v-if="!filteredTerms.length" class="context-empty">没有符合当前筛选条件的领域上下文。</div>
    </div>

    <div v-if="selectedTerm" class="context-drawer-backdrop" @click.self="selectedId = null">
      <aside class="context-drawer">
        <header>
          <div><span class="eyebrow">DOMAIN CONTEXT / TERM</span><h3>{{ selectedTerm.name }}</h3><p>{{ selectedTerm.surface_form }} · {{ typeLabels[selectedTerm.type] }}</p></div>
          <button type="button" @click="selectedId = null">×</button>
        </header>
        <div class="context-drawer-body">
          <div class="context-detail-badges"><span class="context-status-chip" :class="selectedTerm.status">{{ statusLabels[selectedTerm.status] }}</span><span>置信度 {{ Math.round(selectedTerm.confidence * 100) }}%</span><span>出现 {{ selectedTerm.mention_count }} 次</span></div>
          <section><div class="section-head"><h4>论文内定义摘要</h4><span>模型概括 · 非原文</span></div><p class="context-definition-card">{{ selectedTerm.definition }}</p></section>
          <section><div class="section-head"><h4>作者原始表述</h4><span>AUTHOR WORDING</span></div><blockquote>{{ selectedTerm.author_wording }}</blockquote></section>
          <section v-if="selectedTerm.aliases.length"><div class="section-head"><h4>原文写法与别名</h4><span>{{ selectedTerm.aliases.length + 1 }} 个</span></div><div class="context-aliases"><span>{{ selectedTerm.surface_form }}</span><span v-for="alias in selectedTerm.aliases" :key="alias">{{ alias }}</span></div></section>
          <section><div class="section-head"><h4>原文证据</h4><span>{{ selectedTerm.evidence.length }} 条</span></div><article v-for="evidence in selectedTerm.evidence" :key="evidence.id" class="context-evidence-card"><header><span>{{ evidence.kind === 'definition' ? '定义证据' : '使用位置' }}</span><b>{{ evidence.section }} · 第 {{ evidence.page }} 页</b></header><p>{{ evidence.quote }}</p><footer><code>{{ evidence.id }} · {{ evidence.block_id }}</code><button type="button" @click="notice = `已定位到第 ${evidence.page} 页；PDF Viewer 接入后将在原文中高亮。`">定位原文 ↗</button></footer></article></section>
          <section v-if="selectedTerm.related_terms.length"><div class="section-head"><h4>论文内相关概念</h4><span>不表示等价</span></div><div class="context-aliases"><span v-for="term in selectedTerm.related_terms" :key="term">{{ term }}</span></div></section>
          <div v-if="selectedTerm.review_note" class="context-review-note"><strong>审核提示</strong><p>{{ selectedTerm.review_note }}</p></div>
          <div v-if="notice" class="context-notice">{{ notice }}</div>
        </div>
        <footer v-if="!readonly" class="context-drawer-actions"><button class="secondary-action" type="button" @click="review('excluded')">排除候选</button><button class="secondary-action" type="button" @click="notice = '修改定义将在后端 Review API 接入后保存；当前可继续预览交互。'">修改后接受</button><button class="primary-action" type="button" :disabled="selectedTerm.status === 'ambiguous' || selectedTerm.status === 'discovered'" @click="review('evidence_ready')">接受候选</button></footer>
      </aside>
    </div>
  </section>
</template>
