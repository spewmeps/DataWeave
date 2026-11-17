<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createKnowledgeBaseConfiguration,
  getKnowledgeBaseConfiguration,
  getKnowledgeBaseConfigurations,
  updateKnowledgeBaseConfiguration,
} from '@/api/client'
import type { RagflowConfiguration, RagflowConfigurationInput } from '@/types/api'

type PageMode = 'list' | 'detail' | 'form'

const loading = ref(true)
const saving = ref(false)
const mode = ref<PageMode>('list')
const configurations = ref<RagflowConfiguration[]>([])
const selected = ref<RagflowConfiguration | null>(null)
const error = ref('')
const success = ref('')
const form = reactive({ base_url: 'http://localhost:18080', api_key: '', dataset_name: 'DataWeave', language: 'Chinese', parser_id: 'paper' })

const inventory = [
  { data: '业务元数据、版本与映射', service: 'DataWeave', backend: 'SQLite', role: '权威数据' },
  { data: '运行、任务与审核状态', service: 'DataWeave', backend: 'SQLite', role: '权威数据' },
  { data: '结构化字段与增强产物', service: 'DataWeave', backend: 'Local Artifact Store', role: '权威数据' },
  { data: '文章、正文与基础 Chunk', service: 'RAGFlow', backend: 'Dataset / Document Store', role: '目标内容面' },
  { data: '关键词与向量基础索引', service: 'RAGFlow', backend: 'Hybrid Retrieval', role: '目标内容面' },
]

function resetMessages() { error.value = ''; success.value = '' }

function applyToForm(value?: RagflowConfiguration | null) {
  form.base_url = value?.base_url || 'http://localhost:18080'
  form.dataset_name = value?.dataset_name || 'DataWeave'
  form.language = value?.language || 'Chinese'
  form.parser_id = value?.parser_id || 'paper'
  form.api_key = ''
}

async function loadList() {
  loading.value = true
  resetMessages()
  try {
    configurations.value = await getKnowledgeBaseConfigurations()
    mode.value = 'list'
    selected.value = null
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '知识库配置读取失败。'
  } finally { loading.value = false }
}

async function openDetail(item: RagflowConfiguration) {
  if (!item.id) return
  loading.value = true
  resetMessages()
  try {
    selected.value = await getKnowledgeBaseConfiguration(item.id)
    mode.value = 'detail'
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '知识库配置详情读取失败。'
  } finally { loading.value = false }
}

function openCreate() { resetMessages(); selected.value = null; applyToForm(); mode.value = 'form' }
function openEdit() { if (selected.value) { resetMessages(); applyToForm(selected.value); mode.value = 'form' } }

async function save() {
  if (saving.value) return
  saving.value = true
  resetMessages()
  try {
    const input: RagflowConfigurationInput = {
      base_url: form.base_url.trim(), dataset_name: form.dataset_name.trim(),
      language: form.language.trim(), parser_id: form.parser_id,
      ...(form.api_key.trim() ? { api_key: form.api_key.trim() } : {}),
    }
    const saved = selected.value?.id
      ? await updateKnowledgeBaseConfiguration(selected.value.id, input)
      : await createKnowledgeBaseConfiguration(input)
    selected.value = saved
    configurations.value = await getKnowledgeBaseConfigurations()
    mode.value = 'detail'
    const action = saved.dataset_operation === 'created' ? '已通过真实 RAGFlow API 创建' : '已在 RAGFlow 中验证并复用'
    success.value = `知识库“${saved.dataset_name}”${action}，配置已保存到 DataWeave 数据库。`
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'RAGFlow 配置保存失败。'
  } finally { saving.value = false }
}

function dateLabel(value?: string | null) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—' }
function parserLabel(value?: string) { return ({ paper: 'Paper · 论文', general: 'General · 通用', book: 'Book · 书籍', manual: 'Manual · 手册', qa: 'Q&A' } as Record<string, string>)[value || ''] || value || '—' }

onMounted(loadList)
</script>

<template>
  <section class="backend-settings-page">
    <div class="page-heading settings-heading">
      <div><span class="eyebrow">SETTINGS / KNOWLEDGE BASE</span><h1>知识库配置</h1><p>管理 DataWeave 已连接的 RAGFlow 知识库。配置保存在数据库中，点击列表项可查看完整详情。</p></div>
      <button v-if="mode === 'list'" class="primary-action" type="button" @click="openCreate">＋ 添加知识库</button>
      <button v-else class="secondary-action" type="button" @click="loadList">← 返回配置列表</button>
    </div>

    <div v-if="loading" class="center-state">正在读取知识库配置…</div>
    <template v-else>
      <div v-if="error" class="settings-message error"><span>!</span><p>{{ error }}</p></div>
      <div v-if="success" class="settings-message success"><span>✓</span><p>{{ success }}</p></div>

      <div v-if="mode === 'list'" class="knowledge-list-layout">
        <section class="knowledge-list-card">
          <header><div><span class="eyebrow">CONFIGURED KNOWLEDGE BASES</span><h2>已添加的知识库</h2><p>共 {{ configurations.length }} 个配置，数据来自 DataWeave SQLite。</p></div></header>
          <div v-if="!configurations.length" class="knowledge-empty"><span>R</span><h3>还没有知识库配置</h3><p>添加 RAGFlow 服务地址和 API Key，系统会通过真实 API 创建或复用知识库。</p><button class="primary-action" type="button" @click="openCreate">添加第一个知识库</button></div>
          <div v-else class="knowledge-config-list">
            <button v-for="item in configurations" :key="item.id || item.dataset_id || item.dataset_name" type="button" @click="openDetail(item)">
              <span class="provider-logo">R</span>
              <span class="knowledge-list-main"><strong>{{ item.dataset_name }}</strong><small>{{ item.base_url }}</small><code>{{ item.dataset_id }}</code></span>
              <span class="knowledge-list-meta"><em :class="item.status">{{ item.status === 'connected' ? '已连接' : '异常' }}</em><small>更新于 {{ dateLabel(item.updated_at) }}</small></span>
              <b>查看详情 →</b>
            </button>
          </div>
        </section>
        <aside class="storage-policy-card">
          <span class="eyebrow">DATA OWNERSHIP</span><h2>数据存储标记</h2><p>DataWeave API 返回的数据带有 <code>storage_locations</code>，用于说明真实存储位置。</p>
          <div class="storage-policy-list"><article v-for="item in inventory" :key="item.data"><div><strong>{{ item.data }}</strong><small>{{ item.role }}</small></div><span :class="{ ragflow: item.service === 'RAGFlow' }">{{ item.service }}</span><code>{{ item.backend }}</code></article></div>
        </aside>
      </div>

      <section v-else-if="mode === 'detail' && selected" class="knowledge-detail-card">
        <header><div class="provider-logo">R</div><div><span class="eyebrow">RAGFLOW KNOWLEDGE BASE</span><h2>{{ selected.dataset_name }}</h2><p>配置 ID：<code>{{ selected.id }}</code></p></div><span class="provider-status" :class="selected.status">{{ selected.status === 'connected' ? '已连接' : '异常' }}</span></header>
        <div class="knowledge-detail-grid">
          <div><span>API 服务地址</span><strong>{{ selected.base_url }}</strong></div>
          <div><span>API Key</span><strong>{{ selected.api_key_masked }}</strong><small>密钥明文不会返回前端</small></div>
          <div><span>知识库名称</span><strong>{{ selected.dataset_name }}</strong></div>
          <div><span>远端 Dataset ID</span><code>{{ selected.dataset_id }}</code></div>
          <div><span>文档语言</span><strong>{{ selected.language }}</strong></div>
          <div><span>内置解析器</span><strong>{{ parserLabel(selected.parser_id) }}</strong></div>
          <div><span>创建时间</span><strong>{{ dateLabel(selected.created_at) }}</strong></div>
          <div><span>最近验证</span><strong>{{ dateLabel(selected.last_verified_at) }}</strong></div>
          <div><span>最近更新</span><strong>{{ dateLabel(selected.updated_at) }}</strong></div>
          <div><span>配置存储位置</span><strong>DataWeave · SQLite</strong></div>
        </div>
        <footer><p>编辑保存时会再次调用 RAGFlow API 验证连接，并创建或复用指定知识库。</p><button class="primary-action" type="button" @click="openEdit">编辑配置</button></footer>
      </section>

      <section v-else class="backend-config-card knowledge-form-card">
        <header><div class="provider-logo">R</div><div><span class="eyebrow">{{ selected ? 'EDIT CONFIGURATION' : 'NEW CONFIGURATION' }}</span><h2>{{ selected ? '编辑知识库配置' : '添加知识库配置' }}</h2><p>连接 RAGFlow，并将验证成功的配置持久化到 DataWeave 数据库。</p></div></header>
        <form @submit.prevent="save">
          <label class="settings-field"><span>API 服务地址 <b>必填</b></span><input v-model="form.base_url" type="url" required placeholder="http://localhost:18080" /><small>填写 RAGFlow 服务根地址，不包含 `/api/v1`。</small></label>
          <label class="settings-field"><span>API Key <b>{{ selected?.api_key_configured ? '已配置' : '必填' }}</b></span><input v-model="form.api_key" type="password" :required="!selected?.api_key_configured" autocomplete="new-password" :placeholder="selected?.api_key_configured ? '留空以保留现有 Key' : 'ragflow-…'" /><small>{{ selected?.api_key_configured ? `当前密钥：${selected.api_key_masked}。留空不会修改密钥。` : '密钥仅发送到后端并加密保存。' }}</small></label>
          <div class="settings-field-row"><label class="settings-field"><span>知识库名称 <b>必填</b></span><input v-model="form.dataset_name" required maxlength="128" /><small>同名知识库存在时安全复用。</small></label><label class="settings-field"><span>文档语言</span><input v-model="form.language" required maxlength="32" /></label></div>
          <label class="settings-field"><span>内置解析器</span><select v-model="form.parser_id"><option value="paper">Paper · 论文</option><option value="general">General · 通用</option><option value="book">Book · 书籍</option><option value="manual">Manual · 手册</option><option value="qa">Q&A</option></select></label>
          <footer><p>只有 RAGFlow 验证成功后才会写入配置；失败不会覆盖数据库中的原配置。</p><button class="primary-action" type="submit" :disabled="saving">{{ saving ? '正在验证并保存…' : selected ? '保存配置' : '保存并创建知识库' }}</button></footer>
        </form>
      </section>
    </template>
  </section>
</template>
