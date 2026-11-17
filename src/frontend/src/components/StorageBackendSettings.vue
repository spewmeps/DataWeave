<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getRagflowConfiguration, updateRagflowConfiguration } from '@/api/client'
import type { RagflowConfiguration } from '@/types/api'

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const success = ref('')
const configuration = ref<RagflowConfiguration | null>(null)
const form = reactive({
  base_url: 'http://localhost:18080',
  api_key: '',
  dataset_name: 'DataWeave',
  language: 'Chinese',
  parser_id: 'paper',
})

const inventory = [
  { data: '业务元数据、版本与映射', service: 'DataWeave', backend: 'SQLite', role: '权威数据' },
  { data: '运行、任务与审核状态', service: 'DataWeave', backend: 'SQLite', role: '权威数据' },
  { data: '结构化字段与增强产物', service: 'DataWeave', backend: 'Local Artifact Store', role: '权威数据' },
  { data: '文章、正文与基础 Chunk', service: 'RAGFlow', backend: 'Dataset / Document Store', role: '目标内容面' },
  { data: '关键词与向量基础索引', service: 'RAGFlow', backend: 'Hybrid Retrieval', role: '目标内容面' },
]

function applyConfiguration(value: RagflowConfiguration) {
  configuration.value = value
  form.base_url = value.base_url
  form.dataset_name = value.dataset_name
  form.language = value.language
  form.parser_id = value.parser_id
  form.api_key = ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    applyConfiguration(await getRagflowConfiguration())
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '配置读取失败。'
  } finally {
    loading.value = false
  }
}

async function save() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  success.value = ''
  try {
    const input = {
      base_url: form.base_url.trim(),
      dataset_name: form.dataset_name.trim(),
      language: form.language.trim(),
      parser_id: form.parser_id,
      ...(form.api_key.trim() ? { api_key: form.api_key.trim() } : {}),
    }
    const saved = await updateRagflowConfiguration(input)
    applyConfiguration(saved)
    success.value = `连接验证成功，知识库“${saved.dataset_name}”已${saved.dataset_id ? '创建或复用' : '配置'}。`
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'RAGFlow 配置保存失败。'
  } finally {
    saving.value = false
  }
}

function dateLabel(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '尚未验证'
}

onMounted(load)
</script>

<template>
  <section class="backend-settings-page">
    <div class="page-heading settings-heading">
      <div><span class="eyebrow">SETTINGS / STORAGE BACKENDS</span><h1>存储后端配置</h1><p>配置 DataWeave 使用的内容服务，并明确每类数据的权威存储位置。</p></div>
      <div class="tech-status" :class="{ offline: configuration?.status !== 'connected' }"><i /><span>RAGFlow Provider</span><strong>{{ configuration?.status === 'connected' ? 'CONNECTED' : 'NOT CONFIGURED' }}</strong></div>
    </div>

    <div v-if="loading" class="center-state">正在读取存储后端配置…</div>
    <template v-else>
      <div v-if="error" class="settings-message error"><span>!</span><p>{{ error }}</p></div>
      <div v-if="success" class="settings-message success"><span>✓</span><p>{{ success }}</p></div>

      <div class="backend-settings-grid">
        <section class="backend-config-card">
          <header><div class="provider-logo">R</div><div><span class="eyebrow">CONTENT PROVIDER</span><h2>RAGFlow</h2><p>文章、解析 Chunk 和基础混合检索的内容后端。</p></div><span class="provider-status" :class="configuration?.status">{{ configuration?.status === 'connected' ? '已连接' : '待配置' }}</span></header>
          <form @submit.prevent="save">
            <label class="settings-field"><span>API 服务地址 <b>必填</b></span><input v-model="form.base_url" type="url" required placeholder="http://localhost:18080" /><small>填写 RAGFlow 服务根地址，不包含 `/api/v1`。</small></label>
            <label class="settings-field"><span>API Key <b>{{ configuration?.api_key_configured ? '已配置' : '必填' }}</b></span><input v-model="form.api_key" type="password" :required="!configuration?.api_key_configured" autocomplete="new-password" :placeholder="configuration?.api_key_configured ? '留空以保留现有 Key' : 'ragflow-…'" /><small>{{ configuration?.api_key_configured ? `当前密钥：${configuration.api_key_masked}。页面不会读取或回显明文。` : '密钥仅发送到 DataWeave 后端并加密保存。' }}</small></label>
            <div class="settings-field-row">
              <label class="settings-field"><span>默认知识库名称 <b>必填</b></span><input v-model="form.dataset_name" required maxlength="128" placeholder="DataWeave Papers" /><small>保存时在 RAGFlow 中创建；同名知识库存在时安全复用。</small></label>
              <label class="settings-field"><span>文档语言</span><input v-model="form.language" required maxlength="32" /></label>
            </div>
            <label class="settings-field"><span>内置解析器</span><select v-model="form.parser_id"><option value="paper">Paper · 论文</option><option value="general">General · 通用</option><option value="book">Book · 书籍</option><option value="manual">Manual · 手册</option><option value="qa">Q&A</option></select></label>
            <div class="settings-remote-result"><div><span>远端 Dataset ID</span><code>{{ configuration?.dataset_id || '保存配置后生成' }}</code></div><div><span>最近验证</span><strong>{{ dateLabel(configuration?.last_verified_at) }}</strong></div></div>
            <footer><p>保存操作会先验证凭据，并创建或复用填写的知识库；验证失败时不会覆盖现有配置。</p><button class="primary-action" type="submit" :disabled="saving">{{ saving ? '正在验证并创建…' : '保存并创建知识库' }}</button></footer>
          </form>
        </section>

        <aside class="storage-policy-card">
          <span class="eyebrow">DATA OWNERSHIP</span><h2>数据存储标记</h2><p>DataWeave API 返回的文档、运行、任务、模板和产物都带有 <code>storage_locations</code>，用于说明真实存储位置。</p>
          <div class="storage-policy-list"><article v-for="item in inventory" :key="item.data"><div><strong>{{ item.data }}</strong><small>{{ item.role }}</small></div><span :class="{ ragflow: item.service === 'RAGFlow' }">{{ item.service }}</span><code>{{ item.backend }}</code></article></div>
          <div class="storage-policy-note"><span>i</span><p>当前已有文档仍按实际位置标记为 DataWeave 本地文件。后续完成文档同步后，只有成功写入 RAGFlow 的版本才会标记为 RAGFlow。</p></div>
        </aside>
      </div>
    </template>
  </section>
</template>
