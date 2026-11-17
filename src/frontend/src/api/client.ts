import type { AgentTrace, CreateRunResponse, DocumentSummary, PaperTemplate, RagflowConfiguration, RagflowConfigurationInput, RunArtifactManifest, RunSnapshot, TaskNode, UploadRecord } from '@/types/api'

type ApiErrorBody = { detail?: { message?: string } | string }

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody
    const detail = typeof body.detail === 'string' ? body.detail : body.detail?.message
    throw new Error(detail || `请求失败（${response.status}）`)
  }
  return response.json() as Promise<T>
}

export async function getDefaultTemplate(): Promise<PaperTemplate> {
  return parseResponse(await fetch('/api/templates/default'))
}

export async function getDocuments(): Promise<DocumentSummary[]> {
  return parseResponse(await fetch('/api/documents'))
}

export async function getRagflowConfiguration(): Promise<RagflowConfiguration> {
  return parseResponse(await fetch('/api/settings/ragflow'))
}

export async function updateRagflowConfiguration(input: RagflowConfigurationInput): Promise<RagflowConfiguration> {
  return parseResponse(
    await fetch('/api/settings/ragflow', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  )
}

export async function getKnowledgeBaseConfigurations(): Promise<RagflowConfiguration[]> {
  return parseResponse(await fetch('/api/knowledge-bases'))
}

export async function getKnowledgeBaseConfiguration(id: string): Promise<RagflowConfiguration> {
  return parseResponse(await fetch(`/api/knowledge-bases/${encodeURIComponent(id)}`))
}

export async function createKnowledgeBaseConfiguration(input: RagflowConfigurationInput): Promise<RagflowConfiguration> {
  return parseResponse(await fetch('/api/knowledge-bases', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input),
  }))
}

export async function updateKnowledgeBaseConfiguration(id: string, input: RagflowConfigurationInput): Promise<RagflowConfiguration> {
  return parseResponse(await fetch(`/api/knowledge-bases/${encodeURIComponent(id)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input),
  }))
}

export async function executeDocument(documentVersionId: string): Promise<CreateRunResponse> {
  return parseResponse(
    await fetch(`/api/documents/${documentVersionId}/runs`, {
      method: 'POST',
      headers: { 'Idempotency-Key': crypto.randomUUID() },
    }),
  )
}

export function uploadPdf(file: File, onProgress: (progress: number) => void): Promise<UploadRecord> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', '/api/uploads')
    request.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100))
    })
    request.addEventListener('load', () => {
      try {
        const body = JSON.parse(request.responseText) as UploadRecord & ApiErrorBody
        if (request.status < 200 || request.status >= 300) {
          const detail = typeof body.detail === 'string' ? body.detail : body.detail?.message
          reject(new Error(detail || `上传失败（${request.status}）`))
          return
        }
        onProgress(100)
        resolve(body)
      } catch {
        reject(new Error('上传响应无法解析。'))
      }
    })
    request.addEventListener('error', () => reject(new Error('网络连接失败，请确认后端服务已启动。')))
    const form = new FormData()
    form.append('file', file)
    request.send(form)
  })
}

export async function createRun(input: {
  upload: UploadRecord
  template: PaperTemplate
  enabledElements: string[]
  storageTargets: string[]
}): Promise<CreateRunResponse> {
  return parseResponse(
    await fetch('/api/ingestion-runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
      body: JSON.stringify({
        document_id: input.upload.document_id,
        document_version_id: input.upload.document_version_id,
        document_name: input.upload.filename,
        template_id: input.template.id,
        template_version: input.template.version,
        enabled_elements: input.enabledElements,
        storage_targets: input.storageTargets,
      }),
    }),
  )
}

export async function getRun(runId: string): Promise<RunSnapshot> {
  return parseResponse(await fetch(`/api/runs/${runId}`))
}

export async function getTask(runId: string, taskId: string): Promise<TaskNode> {
  return parseResponse(await fetch(`/api/runs/${runId}/tasks/${taskId}`))
}

export async function getRunArtifacts(runId: string): Promise<RunArtifactManifest> {
  return parseResponse(await fetch(`/api/runs/${runId}/artifacts`))
}

export async function getAgentTrace(runId: string, agentId: string): Promise<AgentTrace> {
  return parseResponse(await fetch(`/api/runs/${runId}/agents/${agentId}/trace`))
}

export async function publishRun(runId: string): Promise<RunSnapshot> {
  return parseResponse(await fetch(`/api/runs/${runId}/publish`, { method: 'POST' }))
}

export async function retryRun(runId: string): Promise<CreateRunResponse> {
  return parseResponse(
    await fetch(`/api/runs/${runId}/retry`, {
      method: 'POST',
      headers: { 'Idempotency-Key': crypto.randomUUID() },
    }),
  )
}

