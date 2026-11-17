<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { PaperTemplate } from '@/types/api'

type TemplateKind = 'built_in' | 'custom'
type TemplateSection = 'fields' | 'stores'
type ConfigValue = boolean | string | string[]

interface StoreConfig {
  enabled: boolean
  sourceFields: string[]
  options: Record<string, ConfigValue>
}

type StoreConfigs = Record<string, StoreConfig>
type ManagedTemplate = PaperTemplate & { kind: TemplateKind; updatedAt: string; storeConfigs: StoreConfigs }
type SavePayload = { template: PaperTemplate; keys: string[]; storageTargets: string[] }

interface Choice {
  value: string
  label: string
}

interface ConfigOption {
  key: string
  label: string
  help: string
  type: 'toggle' | 'select' | 'multi'
  choices?: Choice[]
}

interface SchemaField {
  key: string
  type: string
  required: boolean
  description: string
}

interface StoreDefinition {
  id: string
  name: string
  backend: string
  description: string
  sourceCandidates: Choice[]
  options: ConfigOption[]
  schemaFields: SchemaField[]
  runtime: { schema: string; writer: string; source: string }
}

const props = defineProps<{ template: PaperTemplate; activeTemplateId: string; saving: boolean; saved: boolean }>()
const emit = defineEmits<{
  save: [payload: SavePayload]
  'count-change': [count: number]
}>()

const storeDefinitions: StoreDefinition[] = [
  {
    id: 'page_index',
    name: 'PageIndex Store',
    backend: 'Document Store',
    description: '保存文档章节、页面、表格与证据位置，支持从答案回到原文。',
    sourceCandidates: [
      { value: 'paper.title', label: '文档标题' },
      { value: 'paper.author_keywords', label: '作者关键词' },
      { value: 'research.domain_keywords', label: '领域关键词' },
      { value: 'research.problem', label: '研究问题' },
      { value: 'research.contributions', label: '核心贡献' },
      { value: 'method.summary', label: '方法概述' },
      { value: 'experiments.results', label: '实验结果' },
    ],
    options: [
      { key: 'generateSummaries', label: '生成节点摘要', help: '为章节与表格节点生成短摘要，便于定位。', type: 'toggle' },
      { key: 'contentTypes', label: '纳入内容类型', help: '选择需要进入层级索引的文档内容。', type: 'multi', choices: [{ value: 'text', label: '正文' }, { value: 'table', label: '表格' }, { value: 'figure', label: '图片' }] },
      { key: 'minNodeTokens', label: '最小节点长度', help: '短于该值的相邻节点会尝试合并。', type: 'select', choices: [{ value: '200', label: '200 tokens' }, { value: '500', label: '500 tokens' }, { value: '1000', label: '1000 tokens' }] },
    ],
    schemaFields: [
      { key: 'node_id', type: 'string', required: true, description: '层级节点唯一标识' },
      { key: 'parent_id', type: 'string|null', required: false, description: '父节点标识' },
      { key: 'node_type', type: 'enum', required: true, description: '文档、章节、表格或图片' },
      { key: 'path', type: 'string[]', required: true, description: '从根节点到当前节点的路径' },
      { key: 'start_page / end_page', type: 'integer', required: false, description: '原文页面范围' },
      { key: 'block_refs', type: 'string[]', required: true, description: '统一 Document JSON 内容块引用' },
      { key: 'evidence_refs', type: 'string[]', required: true, description: '可追溯证据引用' },
      { key: 'children', type: 'string[]', required: false, description: '子节点标识集合' },
    ],
    runtime: { schema: 'page_index.v1', writer: 'PageIndexWriter', source: 'dataweave.document.v1' },
  },
  {
    id: 'graph',
    name: 'Graph Store',
    backend: 'Graph Database',
    description: '保存实体及可证明关系，支持跨文档关联、路径查询与关系解释。',
    sourceCandidates: [
      { value: 'paper.authors', label: '作者' },
      { value: 'paper.affiliations', label: '机构与国家' },
      { value: 'research.domain_keywords', label: '领域关键词' },
      { value: 'research.innovation_keywords', label: '创新关键词' },
      { value: 'research.contributions', label: '核心贡献' },
      { value: 'method.summary', label: '方法概述' },
      { value: 'experiments.datasets', label: '实验数据集' },
    ],
    options: [
      { key: 'entityTypes', label: '实体类型', help: '选择需要构建为图节点的业务实体。', type: 'multi', choices: [{ value: 'person', label: '人员' }, { value: 'organization', label: '机构' }, { value: 'method', label: '方法' }, { value: 'dataset', label: '数据集' }, { value: 'claim', label: '结论' }] },
      { key: 'mergeEntities', label: '同名实体合并', help: '对标准名与别名相近的实体执行归一化。', type: 'toggle' },
    ],
    schemaFields: [
      { key: 'entity_id', type: 'string', required: true, description: '实体唯一标识' },
      { key: 'entity_type', type: 'enum', required: true, description: '人员、机构、方法、数据集或结论' },
      { key: 'canonical_name', type: 'string', required: true, description: '实体标准名称' },
      { key: 'aliases', type: 'string[]', required: false, description: '实体别名' },
      { key: 'source_id / target_id', type: 'string', required: true, description: '关系起点与终点' },
      { key: 'relation_type', type: 'string', required: true, description: '关系类型' },
      { key: 'properties', type: 'object', required: false, description: '实体或关系扩展属性' },
      { key: 'evidence_refs / confidence', type: 'array / number', required: true, description: '关系证据与置信度' },
    ],
    runtime: { schema: 'knowledge_graph.v1', writer: 'GraphWriter', source: 'dataweave.document.v1' },
  },
  {
    id: 'tree',
    name: 'Tree Store',
    backend: 'Hierarchy Store',
    description: '保存领域分类树与文档归属，用于研究方向导航和覆盖度分析。',
    sourceCandidates: [
      { value: 'research.domain_keywords', label: '领域关键词' },
      { value: 'research.innovation_keywords', label: '创新关键词' },
      { value: 'research.problem', label: '研究问题' },
      { value: 'research.contributions', label: '核心贡献' },
      { value: 'method.summary', label: '方法概述' },
    ],
    options: [
      { key: 'taxonomy', label: '分类体系', help: '选择用于挂载文档的内置分类树。', type: 'select', choices: [{ value: 'research_domain_v1', label: '研究领域 v1' }, { value: 'technology_v1', label: '技术体系 v1' }] },
      { key: 'multiLabel', label: '允许多路径归属', help: '同一文档可归属到多个研究方向。', type: 'toggle' },
      { key: 'threshold', label: '归属阈值', help: '低于阈值的候选分类进入待确认状态。', type: 'select', choices: [{ value: '0.60', label: '0.60 宽松' }, { value: '0.75', label: '0.75 推荐' }, { value: '0.90', label: '0.90 严格' }] },
    ],
    schemaFields: [
      { key: 'taxonomy_id / version', type: 'string', required: true, description: '分类体系及版本' },
      { key: 'node_id / parent_id', type: 'string', required: true, description: '分类节点与父节点' },
      { key: 'path / level', type: 'array / integer', required: true, description: '层级路径与深度' },
      { key: 'code / label', type: 'string', required: true, description: '分类编码与展示名称' },
      { key: 'target_id / target_type', type: 'string', required: true, description: '被分类对象' },
      { key: 'score', type: 'number', required: true, description: '归属置信度' },
      { key: 'evidence_refs', type: 'string[]', required: true, description: '支持分类判断的证据' },
      { key: 'is_primary', type: 'boolean', required: true, description: '是否为主分类路径' },
    ],
    runtime: { schema: 'taxonomy_assignment.v1', writer: 'TreeWriter', source: 'dataweave.document.v1' },
  },
  {
    id: 'hybrid_retrieval',
    name: 'Hybrid Retrieval Store',
    backend: 'Search + Vector',
    description: '保存全文、字段、向量与过滤元数据，同时支持关键词和语义召回。',
    sourceCandidates: [
      { value: 'paper.title', label: '文档标题' },
      { value: 'paper.author_keywords', label: '作者关键词' },
      { value: 'research.domain_keywords', label: '领域关键词' },
      { value: 'research.innovation_keywords', label: '创新关键词' },
      { value: 'research.problem', label: '研究问题' },
      { value: 'research.contributions', label: '核心贡献' },
      { value: 'method.summary', label: '方法概述' },
      { value: 'experiments.results', label: '实验结果' },
    ],
    options: [
      { key: 'indexLevels', label: '索引粒度', help: '决定检索可以命中文档、章节、片段或结构化字段。', type: 'multi', choices: [{ value: 'document', label: '文档' }, { value: 'section', label: '章节' }, { value: 'chunk', label: '片段' }, { value: 'field', label: '字段' }] },
      { key: 'chunkSize', label: '片段长度', help: '用于语义检索的目标片段长度。', type: 'select', choices: [{ value: '500', label: '500 tokens' }, { value: '800', label: '800 tokens' }, { value: '1200', label: '1200 tokens' }] },
      { key: 'chunkOverlap', label: '片段重叠', help: '保留跨片段语义连续性的重叠长度。', type: 'select', choices: [{ value: '80', label: '80 tokens' }, { value: '120', label: '120 tokens' }, { value: '200', label: '200 tokens' }] },
    ],
    schemaFields: [
      { key: 'record_id / document_id', type: 'string', required: true, description: '检索记录与文档标识' },
      { key: 'level', type: 'enum', required: true, description: '文档、章节、片段或字段' },
      { key: 'title / text', type: 'string', required: true, description: '可检索标题与正文' },
      { key: 'section_path / chunk_index', type: 'array / integer', required: false, description: '章节路径与片段顺序' },
      { key: 'embedding', type: 'vector', required: true, description: '系统生成的语义向量' },
      { key: 'embedding_model', type: 'string', required: true, description: '向量模型版本' },
      { key: 'metadata / acl', type: 'object', required: true, description: '过滤元数据与访问控制' },
      { key: 'evidence_refs / content_hash', type: 'array / string', required: true, description: '原文证据与内容指纹' },
    ],
    runtime: { schema: 'hybrid_record.v1', writer: 'HybridRetrievalWriter', source: 'dataweave.document.v1' },
  },
]

const defaultOptions: Record<string, Record<string, ConfigValue>> = {
  page_index: { generateSummaries: true, contentTypes: ['text', 'table', 'figure'], minNodeTokens: '500' },
  graph: { entityTypes: ['person', 'organization', 'method', 'dataset', 'claim'], mergeEntities: true },
  tree: { taxonomy: 'research_domain_v1', multiLabel: true, threshold: '0.75' },
  hybrid_retrieval: { indexLevels: ['document', 'section', 'chunk', 'field'], chunkSize: '800', chunkOverlap: '120' },
}

function cloneSerializable<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function createDefaultStoreConfigs(): StoreConfigs {
  return Object.fromEntries(storeDefinitions.map((store) => [store.id, {
    enabled: true,
    sourceFields: store.sourceCandidates.map((item) => item.value),
    options: cloneSerializable(defaultOptions[store.id]),
  }]))
}

function cloneStoreConfigs(configs: StoreConfigs): StoreConfigs {
  // Vue wraps template state in Proxy objects; clone only its serializable config data.
  return cloneSerializable(configs)
}

function normalizeStoreConfigs(configs?: StoreConfigs): StoreConfigs {
  const defaults = createDefaultStoreConfigs()
  if (!configs) return defaults
  for (const store of storeDefinitions) {
    const saved = configs[store.id]
    if (!saved) continue
    defaults[store.id] = {
      enabled: saved.enabled ?? true,
      sourceFields: Array.isArray(saved.sourceFields) ? [...saved.sourceFields] : defaults[store.id].sourceFields,
      options: { ...defaults[store.id].options, ...(saved.options || {}) },
    }
  }
  return defaults
}

const storageKey = 'dataweave.customTemplates'
const overrideKey = 'dataweave.templateStoreOverrides'

function loadOverrides(): Record<string, StoreConfigs> {
  if (typeof window === 'undefined') return {}
  try {
    return JSON.parse(window.localStorage.getItem(overrideKey) || '{}') as Record<string, StoreConfigs>
  } catch {
    return {}
  }
}

const savedOverrides = loadOverrides()
const builtInTemplate: ManagedTemplate = {
  ...props.template,
  kind: 'built_in',
  updatedAt: '系统内置',
  storeConfigs: normalizeStoreConfigs(savedOverrides[props.template.id]),
}

function loadCustomTemplates(): ManagedTemplate[] {
  if (typeof window === 'undefined') return []
  try {
    const value = JSON.parse(window.localStorage.getItem(storageKey) || '[]') as ManagedTemplate[]
    return value
      .filter((item) => item?.id && item?.name && Array.isArray(item.elements))
      .map((item) => ({ ...item, kind: 'custom', storeConfigs: normalizeStoreConfigs(item.storeConfigs) }))
  } catch {
    return []
  }
}

const templates = ref<ManagedTemplate[]>([builtInTemplate, ...loadCustomTemplates()])
const activeId = ref(templates.value.some((item) => item.id === props.activeTemplateId) ? props.activeTemplateId : builtInTemplate.id)
const appliedTemplateId = ref(props.activeTemplateId)
const selected = ref(new Set<string>())
const focusedKey = ref('')
const activeSection = ref<TemplateSection>('fields')
const selectedStoreId = ref(storeDefinitions[0].id)
const editingStoreConfigs = ref<StoreConfigs>(createDefaultStoreConfigs())
const systemDetailsOpen = ref<Record<string, boolean>>({})
const fieldRulesOpen = ref(false)
const configMessage = ref('')
const showCreate = ref(false)
const newName = ref('')
const newDescription = ref('')
const formError = ref('')

const currentTemplate = computed(() => templates.value.find((item) => item.id === activeId.value) || templates.value[0])
const focused = computed(() => currentTemplate.value?.elements.find((item) => item.key === focusedKey.value))
const requiredCount = computed(() => currentTemplate.value?.elements.filter((item) => item.required).length || 0)
const customCount = computed(() => templates.value.filter((item) => item.kind === 'custom').length)
const selectedStore = computed(() => storeDefinitions.find((item) => item.id === selectedStoreId.value) || storeDefinitions[0])
const selectedStoreConfig = computed(() => editingStoreConfigs.value[selectedStore.value.id])
const enabledStoreCount = computed(() => Object.values(editingStoreConfigs.value).filter((item) => item.enabled).length)

watch(currentTemplate, (next) => {
  if (!next) return
  selected.value = new Set(next.elements.filter((item) => item.enabled).map((item) => item.key))
  focusedKey.value = next.elements[0]?.key || ''
  editingStoreConfigs.value = cloneStoreConfigs(normalizeStoreConfigs(next.storeConfigs))
  selectedStoreId.value = storeDefinitions[0].id
  systemDetailsOpen.value = {}
  configMessage.value = ''
}, { immediate: true })

watch(focusedKey, () => {
  fieldRulesOpen.value = false
})

onMounted(() => emit('count-change', templates.value.length))

function persistCustomTemplates() {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(storageKey, JSON.stringify(templates.value.filter((item) => item.kind === 'custom')))
}

function persistOverride(templateId: string, configs: StoreConfigs) {
  if (typeof window === 'undefined') return
  const overrides = loadOverrides()
  overrides[templateId] = configs
  window.localStorage.setItem(overrideKey, JSON.stringify(overrides))
}

function chooseTemplate(id: string) {
  activeId.value = id
}

function toggle(key: string, required: boolean) {
  if (required) return
  const next = new Set(selected.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  selected.value = next
}

function toggleStoreEnabled(id: string) {
  editingStoreConfigs.value[id].enabled = !editingStoreConfigs.value[id].enabled
  configMessage.value = ''
}

function toggleSourceField(value: string) {
  const config = selectedStoreConfig.value
  config.sourceFields = config.sourceFields.includes(value)
    ? config.sourceFields.filter((item) => item !== value)
    : [...config.sourceFields, value]
  configMessage.value = ''
}

function toggleMultiOption(key: string, value: string) {
  const current = selectedStoreConfig.value.options[key]
  const values = Array.isArray(current) ? current : []
  selectedStoreConfig.value.options[key] = values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value]
  configMessage.value = ''
}

function isMultiSelected(key: string, value: string) {
  const current = selectedStoreConfig.value.options[key]
  return Array.isArray(current) && current.includes(value)
}

function setSelectOption(key: string, event: Event) {
  selectedStoreConfig.value.options[key] = (event.target as HTMLSelectElement).value
  configMessage.value = ''
}

function openCreate() {
  newName.value = ''
  newDescription.value = ''
  formError.value = ''
  showCreate.value = true
}

function createTemplate() {
  const name = newName.value.trim()
  if (!name) {
    formError.value = '请输入模板名称。'
    return
  }
  const now = new Date()
  const created: ManagedTemplate = {
    id: `paper_custom_${now.getTime()}`,
    name,
    version: 1,
    description: newDescription.value.trim() || '基于内置论文模板创建，可继续调整提取字段、证据规则与输出存储。',
    elements: builtInTemplate.elements.map((item) => ({ ...item, section_hints: [...item.section_hints] })),
    storeConfigs: cloneStoreConfigs(builtInTemplate.storeConfigs),
    kind: 'custom',
    updatedAt: '刚刚更新',
  }
  templates.value = [...templates.value, created]
  persistCustomTemplates()
  emit('count-change', templates.value.length)
  activeId.value = created.id
  showCreate.value = false
}

function validateConfiguration() {
  const invalid = storeDefinitions.filter((store) => {
    const config = editingStoreConfigs.value[store.id]
    return config.enabled && config.sourceFields.length === 0
  })
  configMessage.value = invalid.length ? `${invalid.map((item) => item.name).join('、')} 至少需要选择一个字段来源。` : '配置检查通过，可以应用到后续解析任务。'
}

function saveCurrentTemplate() {
  if (!currentTemplate.value) return
  const updatedElements = currentTemplate.value.elements.map((item) => ({ ...item, enabled: selected.value.has(item.key) }))
  const storeConfigs = cloneStoreConfigs(editingStoreConfigs.value)
  const updated: ManagedTemplate = { ...currentTemplate.value, elements: updatedElements, storeConfigs, updatedAt: '刚刚更新' }
  templates.value = templates.value.map((item) => item.id === updated.id ? updated : item)
  persistCustomTemplates()
  persistOverride(updated.id, storeConfigs)
  appliedTemplateId.value = updated.id
  emit('save', {
    template: updated,
    keys: [...selected.value],
    storageTargets: storeDefinitions.filter((item) => storeConfigs[item.id].enabled).map((item) => item.id),
  })
}
</script>

<template>
  <section class="template-library">
    <aside class="template-catalog">
      <div class="catalog-head">
        <div><span class="eyebrow">TEMPLATE LIBRARY</span><h2>模板列表</h2></div>
        <button class="catalog-create" type="button" title="新建模板" @click="openCreate">＋</button>
      </div>

      <div class="catalog-summary">
        <span><strong>{{ templates.length }}</strong> 全部模板</span>
        <span><strong>{{ customCount }}</strong> 自定义</span>
      </div>

      <div class="catalog-list">
        <button v-for="item in templates" :key="item.id" type="button" class="template-card" :class="{ active: activeId === item.id }" @click="chooseTemplate(item.id)">
          <span class="template-card-icon">{{ item.kind === 'built_in' ? '论文' : '自定' }}</span>
          <span class="template-card-copy">
            <span class="template-card-title"><strong>{{ item.name }}</strong><em v-if="item.kind === 'built_in'">内置</em></span>
            <small>{{ item.elements.length }} 个字段 · {{ Object.values(item.storeConfigs).filter((store) => store.enabled).length }} 个存储</small>
            <small>{{ item.updatedAt }}</small>
          </span>
          <i v-if="appliedTemplateId === item.id" title="当前使用" />
        </button>
      </div>

      <button class="new-template-button" type="button" @click="openCreate"><span>＋</span><div><strong>新建模板</strong><small>复制论文模板快速开始</small></div></button>
    </aside>

    <div v-if="currentTemplate" class="stage-card template-stage">
      <header class="template-head">
        <div>
          <div class="template-title-line"><span class="eyebrow">TEMPLATE / DETAILS</span><b>{{ currentTemplate.kind === 'built_in' ? 'BUILT-IN' : 'CUSTOM' }}</b></div>
          <h2>{{ currentTemplate.name }}</h2>
          <p>{{ currentTemplate.description }}</p>
        </div>
        <div class="template-badges">
          <span v-if="saved && appliedTemplateId === currentTemplate.id" class="success-chip">配置已保存</span>
          <span class="version-chip">{{ currentTemplate.kind === 'built_in' ? 'Published' : 'Draft' }} v{{ currentTemplate.version }}</span>
        </div>
      </header>

      <div class="template-overview">
        <div><span>模板类型</span><strong>{{ currentTemplate.kind === 'built_in' ? '内置论文模板' : '自定义模板' }}</strong></div>
        <div><span>提取字段</span><strong>{{ currentTemplate.elements.length }} 个</strong></div>
        <div><span>输出存储</span><strong>{{ enabledStoreCount }} / {{ storeDefinitions.length }} 已启用</strong></div>
        <div><span>运行状态</span><strong>{{ appliedTemplateId === currentTemplate.id ? '当前使用' : '未启用' }}</strong></div>
      </div>

      <nav class="template-section-tabs" aria-label="模板配置模块">
        <button type="button" :class="{ active: activeSection === 'fields' }" @click="activeSection = 'fields'">
          <span>01</span><div><strong>提取字段</strong><small>用户选择需要提取的信息</small></div><em>{{ selected.size }}</em>
        </button>
        <button type="button" :class="{ active: activeSection === 'stores' }" @click="activeSection = 'stores'">
          <span>02</span><div><strong>输出存储</strong><small>配置字段如何投影到存储介质</small></div><em>{{ enabledStoreCount }}</em>
        </button>
      </nav>

      <div v-if="activeSection === 'fields'" class="template-workspace">
        <div class="element-list">
          <div class="element-list-head"><strong>需要用户配置 · 提取元素</strong><span>{{ selected.size }} / {{ currentTemplate.elements.length }}</span></div>
          <button v-for="item in currentTemplate.elements" :key="item.key" type="button" class="element-row" :class="{ focused: focusedKey === item.key }" @click="focusedKey = item.key">
            <span class="element-check" :class="{ checked: selected.has(item.key), locked: item.required }" @click.stop="toggle(item.key, item.required)">{{ selected.has(item.key) ? '✓' : '' }}</span>
            <span><strong>{{ item.label }}</strong><small>{{ item.key }}</small></span>
            <em>{{ item.type }}</em>
          </button>
        </div>

        <div v-if="focused" class="element-detail">
          <div class="detail-kicker">FIELD CONFIGURATION</div>
          <div class="detail-title"><div><h3>{{ focused.label }}</h3><code>{{ focused.key }}</code></div><span>{{ focused.type }}</span></div>
          <section class="user-config-panel field-user-config">
            <div class="panel-title"><div><span>需要用户配置</span><h4>是否提取此字段</h4></div><b>USER CONFIG</b></div>
            <div class="primary-config-row">
              <div><strong>{{ selected.has(focused.key) ? '已加入提取任务' : '已从提取任务移除' }}</strong><small>{{ focused.required ? '必填字段由模板保证启用，不能关闭。' : '可按当前业务场景决定是否提取。' }}</small></div>
              <button type="button" class="toggle-switch" :class="{ on: selected.has(focused.key) }" :disabled="focused.required" :aria-pressed="selected.has(focused.key)" @click="toggle(focused.key, focused.required)"><i /></button>
            </div>
          </section>
          <section class="readonly-disclosure field-rule-disclosure" :class="{ open: fieldRulesOpen }">
            <button type="button" class="disclosure-trigger" @click="fieldRulesOpen = !fieldRulesOpen">
              <span class="lock-symbol">▣</span><div><strong>内置提取规则与运行时 Schema</strong><small>系统已配置证据、章节提示和抽取规范，无需用户编辑。</small></div><em>系统内置</em><b>{{ fieldRulesOpen ? '收起 ↑' : '查看 ↓' }}</b>
            </button>
            <div v-if="fieldRulesOpen" class="readonly-content field-rule-content">
              <div class="readonly-notice"><span>只读</span>以下规则随模板版本发布，用户不能修改。</div>
              <div class="config-grid">
                <label><span>是否必填</span><strong>{{ focused.required ? 'Required' : 'Optional' }}</strong></label>
                <label><span>证据要求</span><strong>必须绑定原文</strong></label>
              </div>
              <div class="config-block"><span>优先章节</span><div><b v-for="section in focused.section_hints" :key="section">{{ section }}</b></div></div>
              <div class="config-block"><span>抽取说明</span><p>{{ focused.guideline }}</p></div>
              <div class="schema-preview">
                <div><span>运行时 Schema</span><small>READ ONLY</small></div>
                <pre>{
  "key": "{{ focused.key }}",
  "type": "{{ focused.type }}",
  "required": {{ focused.required }},
  "evidence_required": true
}</pre>
              </div>
            </div>
          </section>
        </div>
      </div>

      <div v-else class="store-workspace">
        <aside class="store-list">
          <div class="store-list-head"><div><strong>输出存储</strong><small>选择一个存储目标进行配置</small></div><span>{{ enabledStoreCount }} / 4</span></div>
          <button v-for="store in storeDefinitions" :key="store.id" type="button" class="store-card" :class="{ active: selectedStoreId === store.id, disabled: !editingStoreConfigs[store.id].enabled }" @click="selectedStoreId = store.id">
            <span class="store-symbol">{{ store.id === 'page_index' ? '▤' : store.id === 'graph' ? '◇' : store.id === 'tree' ? '⌘' : '⌕' }}</span>
            <span><strong>{{ store.name }}</strong><small>{{ store.backend }}</small></span>
            <i :class="{ on: editingStoreConfigs[store.id].enabled }">{{ editingStoreConfigs[store.id].enabled ? 'ON' : 'OFF' }}</i>
          </button>
        </aside>

        <section class="store-detail">
          <header class="store-detail-head">
            <div><span class="detail-kicker">STORE PROJECTION</span><h3>{{ selectedStore.name }}</h3><p>{{ selectedStore.description }}</p></div>
            <div><span class="system-badge">系统内置能力</span><small>{{ selectedStore.backend }}</small></div>
          </header>

          <section class="user-config-panel">
            <div class="panel-title"><div><span>需要用户配置</span><h4>运行与字段映射</h4></div><b>USER CONFIG</b></div>

            <div class="primary-config-row">
              <div><strong>启用此存储目标</strong><small>关闭后，本模板的解析任务将跳过该存储写入。</small></div>
              <button type="button" class="toggle-switch" :class="{ on: selectedStoreConfig.enabled }" :aria-pressed="selectedStoreConfig.enabled" @click="toggleStoreEnabled(selectedStore.id)"><i /></button>
            </div>

            <div class="field-mapping-config" :class="{ muted: !selectedStoreConfig.enabled }">
              <div class="config-heading"><div><strong>字段来源</strong><small>选择统一 Document JSON 中需要投影到该存储的结构化字段。</small></div><em>{{ selectedStoreConfig.sourceFields.length }} 已选</em></div>
              <div class="choice-chips">
                <button v-for="field in selectedStore.sourceCandidates" :key="field.value" type="button" :class="{ selected: selectedStoreConfig.sourceFields.includes(field.value) }" :disabled="!selectedStoreConfig.enabled" @click="toggleSourceField(field.value)"><span>{{ selectedStoreConfig.sourceFields.includes(field.value) ? '✓' : '＋' }}</span>{{ field.label }}<small>{{ field.value }}</small></button>
              </div>
            </div>

            <div class="store-option-grid" :class="{ muted: !selectedStoreConfig.enabled }">
              <article v-for="option in selectedStore.options" :key="option.key" class="store-option">
                <div><strong>{{ option.label }}</strong><small>{{ option.help }}</small></div>
                <button v-if="option.type === 'toggle'" type="button" class="toggle-switch compact-toggle" :class="{ on: selectedStoreConfig.options[option.key] }" :disabled="!selectedStoreConfig.enabled" @click="selectedStoreConfig.options[option.key] = !selectedStoreConfig.options[option.key]"><i /></button>
                <select v-else-if="option.type === 'select'" :value="selectedStoreConfig.options[option.key]" :disabled="!selectedStoreConfig.enabled" @change="setSelectOption(option.key, $event)">
                  <option v-for="choice in option.choices" :key="choice.value" :value="choice.value">{{ choice.label }}</option>
                </select>
                <div v-else class="inline-choice-list">
                  <button v-for="choice in option.choices" :key="choice.value" type="button" :class="{ selected: isMultiSelected(option.key, choice.value) }" :disabled="!selectedStoreConfig.enabled" @click="toggleMultiOption(option.key, choice.value)">{{ choice.label }}</button>
                </div>
              </article>
            </div>
          </section>

          <section class="readonly-disclosure" :class="{ open: systemDetailsOpen[selectedStore.id] }">
            <button type="button" class="disclosure-trigger" @click="systemDetailsOpen[selectedStore.id] = !systemDetailsOpen[selectedStore.id]">
              <span class="lock-symbol">▣</span><div><strong>内置 Schema 与运行能力</strong><small>无需配置；需要核查时可展开查看字段结构和写入器。</small></div><em>{{ selectedStore.schemaFields.length }} 个字段</em><b>{{ systemDetailsOpen[selectedStore.id] ? '收起 ↑' : '查看 ↓' }}</b>
            </button>
            <div v-if="systemDetailsOpen[selectedStore.id]" class="readonly-content">
              <div class="readonly-notice"><span>只读</span>以下结构由系统版本管理，模板用户不能编辑。</div>
              <div class="runtime-cards">
                <div><span>Schema</span><strong>{{ selectedStore.runtime.schema }}</strong></div>
                <div><span>Writer</span><strong>{{ selectedStore.runtime.writer }}</strong></div>
                <div><span>Source</span><strong>{{ selectedStore.runtime.source }}</strong></div>
              </div>
              <div class="schema-field-list">
                <div class="schema-field-head"><span>字段</span><span>类型</span><span>约束</span><span>说明</span></div>
                <div v-for="field in selectedStore.schemaFields" :key="field.key" class="schema-field-row"><code>{{ field.key }}</code><span>{{ field.type }}</span><b>{{ field.required ? 'Required' : 'Optional' }}</b><p>{{ field.description }}</p></div>
              </div>
              <p class="system-config-note">数据库连接、索引名称、向量模型与鉴权策略属于系统设置，由管理员统一维护，不进入模板编辑范围。</p>
            </div>
          </section>
        </section>
      </div>

      <footer class="template-footer">
        <div v-if="activeSection === 'fields'"><strong>{{ selected.size }} 个字段将在文档上传后自动提取</strong><span>其中 {{ requiredCount }} 个必填字段 · 运行时 Schema 为内置只读能力</span></div>
        <div v-else><strong>{{ enabledStoreCount }} 个存储目标将在 Document JSON 生成后执行</strong><span>用户只配置字段映射与运行策略 · 存储结构和写入能力由系统维护</span><small v-if="configMessage" class="config-message" :class="{ error: configMessage.includes('至少') }">{{ configMessage }}</small></div>
        <div><button class="secondary-action" type="button" @click="validateConfiguration">检查配置</button><button class="primary-action" type="button" :disabled="saving" @click="saveCurrentTemplate">{{ saving ? '保存中…' : '保存并设为当前模板' }}</button></div>
      </footer>
    </div>

    <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
      <form class="template-modal" @submit.prevent="createTemplate">
        <div class="modal-head"><div><span class="eyebrow">CREATE TEMPLATE</span><h2>新建提取模板</h2></div><button type="button" @click="showCreate = false">×</button></div>
        <p>从内置论文模板复制提取字段、证据规则和输出存储配置，创建后可独立调整用户配置。</p>
        <label class="modal-field"><span>模板名称</span><input v-model="newName" maxlength="40" placeholder="例如：大模型论文分析" autofocus /></label>
        <label class="modal-field"><span>模板说明</span><textarea v-model="newDescription" maxlength="160" rows="3" placeholder="说明该模板适用的文档类型或分析目标" /></label>
        <div class="template-source"><span>复制来源</span><div><b>论文结构化分析</b><small>{{ builtInTemplate.elements.length }} 个字段 · {{ storeDefinitions.length }} 个输出存储</small></div><em>内置</em></div>
        <div v-if="formError" class="form-error">{{ formError }}</div>
        <footer><button class="secondary-action" type="button" @click="showCreate = false">取消</button><button class="primary-action" type="submit">创建模板</button></footer>
      </form>
    </div>
  </section>
</template>
