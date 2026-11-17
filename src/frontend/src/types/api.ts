export type TaskStatus =
  | 'pending'
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'retrying'
  | 'skipped'
  | 'cancelled'

export type RunStatus =
  | 'created'
  | 'queued'
  | 'running'
  | 'awaiting_review'
  | 'partially_completed'
  | 'failed'
  | 'cancelled'
  | 'published'

export interface StorageLocation {
  service: string
  backend: string
  role: string
  authoritative: boolean
  resource_id?: string | null
}

export interface UploadRecord {
  upload_id: string
  document_id: string
  document_version_id: string
  filename: string
  size: number
  sha256: string
  duplicate: boolean
  status: string
  created_at: string
  storage_locations: StorageLocation[]
}

export interface DocumentSummary {
  document_id: string
  document_version_id: string
  filename: string
  size: number
  uploaded_at: string
  upload_status: string
  run_id?: string | null
  run_status?: string | null
  progress: number
  completed_tasks: number
  total_tasks: number
  current_task?: string | null
  template_version?: number | null
  storage_locations: StorageLocation[]
}

export interface TemplateElement {
  key: string
  label: string
  type: string
  required: boolean
  enabled: boolean
  section_hints: string[]
  guideline: string
}

export interface PaperTemplate {
  id: string
  name: string
  version: number
  description: string
  elements: TemplateElement[]
  storage_locations?: StorageLocation[]
}

export interface Metric {
  name: string
  label: string
  value: string | number
  unit?: string | null
}

export interface FieldEvidence {
  quote: string
  page_idx?: number | null
  section?: string | null
}

export interface SchemaFieldResult {
  key: string
  label: string
  type: string
  status: 'extracted' | 'missing' | 'invalid'
  value: unknown
  confidence: number
  evidence: FieldEvidence[]
}

export interface AgentTraceEvent {
  timestamp: string
  level: string
  event: string
  message?: string | null
  payload: Record<string, unknown>
  exception?: string | null
  source: 'agent_log' | 'task_snapshot' | string
}

export interface AgentTrace {
  run_id: string
  agent_id: string
  agent_name: string
  status: string
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  log_path: string
  detailed_trace_available: boolean
  events: AgentTraceEvent[]
  result: {
    fields: SchemaFieldResult[]
    field_count: number
    extracted: number
    missing: number
    invalid: number
  }
}

export interface TaskNode {
  id: string
  name: string
  kind: string
  description: string
  executor: string
  status: TaskStatus
  attempt: number
  max_attempts: number
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  input: Record<string, unknown>
  output: Record<string, unknown>
  metrics: Metric[]
  warnings: string[]
  children: TaskNode[]
  storage_locations: StorageLocation[]
}

export interface RunSnapshot {
  id: string
  document_id: string
  document_version_id: string
  document_name: string
  template_id: string
  template_version: number
  retry_of_run_id?: string | null
  retry_number: number
  status: RunStatus
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  last_activity_at: string
  progress: {
    completed: number
    total: number
    percent: number
    current_task?: string | null
  }
  tasks: TaskNode[]
  result_summary: Record<string, unknown>
  storage_locations: StorageLocation[]
}

export interface CreateRunResponse {
  run_id: string
  status: string
  links: Record<string, string>
  storage_locations: StorageLocation[]
}

export interface RagflowConfiguration {
  provider: 'ragflow'
  base_url: string
  api_key_configured: boolean
  api_key_masked?: string | null
  dataset_name: string
  dataset_id?: string | null
  language: string
  parser_id: string
  status: 'not_configured' | 'connected' | 'error'
  last_verified_at?: string | null
  updated_at?: string | null
  storage_locations: StorageLocation[]
}

export interface RagflowConfigurationInput {
  base_url: string
  api_key?: string
  dataset_name: string
  language: string
  parser_id: string
}

export type DomainContextTermType = 'new_term' | 'method' | 'acronym' | 'dataset' | 'metric'

export type DomainContextTermStatus =
  | 'discovered'
  | 'evidence_ready'
  | 'review_pending'
  | 'ambiguous'
  | 'excluded'
  | 'published'

export interface DomainContextEvidence {
  id: string
  section: string
  page: number
  quote: string
  block_id: string
  kind: 'definition' | 'usage'
}

export interface DomainContextTerm {
  id: string
  name: string
  surface_form: string
  type: DomainContextTermType
  status: DomainContextTermStatus
  definition: string
  author_wording: string
  aliases: string[]
  confidence: number
  mention_count: number
  evidence: DomainContextEvidence[]
  related_terms: string[]
  review_note?: string
}

export interface DomainContextArtifact {
  id: string
  run_id: string
  document_id: string
  document_version_id: string
  document_name: string
  status: 'draft' | 'review_pending' | 'published' | 'partial'
  scope: 'document'
  release_version?: number | null
  schema_version: string
  generated_at: string
  evidence_coverage: number
  terms: DomainContextTerm[]
}

