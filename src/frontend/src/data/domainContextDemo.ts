import type { DomainContextArtifact, DomainContextTerm, RunSnapshot, TaskNode, TaskStatus } from '@/types/api'

const terms: DomainContextTerm[] = [
  {
    id: 'term_adaclip_x',
    name: 'AdaClip-X',
    surface_form: 'AdaClip-X',
    type: 'method',
    status: 'evidence_ready',
    definition: '一种根据训练状态动态调整裁剪阈值的方法，用于改善策略优化过程的稳定性。',
    author_wording: 'We introduce AdaClip-X, an adaptive clipping schedule that changes the clipping threshold according to optimization dynamics.',
    aliases: ['Adaptive Clipping X'],
    confidence: 0.94,
    mention_count: 11,
    evidence: [
      { id: 'ev_ctx_001', section: '3.1 Adaptive Clipping', page: 4, block_id: 'block_3_1_02', kind: 'definition', quote: 'We introduce AdaClip-X, an adaptive clipping schedule that changes the clipping threshold according to optimization dynamics.' },
      { id: 'ev_ctx_002', section: '4.2 Experiments', page: 7, block_id: 'block_4_2_06', kind: 'usage', quote: 'AdaClip-X remains stable under all evaluated training configurations and consistently improves the final reward.' },
    ],
    related_terms: ['PPO', 'Clipping threshold', 'Training stability'],
  },
  {
    id: 'term_dat',
    name: 'DAT',
    surface_form: 'DAT',
    type: 'acronym',
    status: 'ambiguous',
    definition: '当前论文中存在两个可能的缩写展开，需要人工确认其作用域。',
    author_wording: 'DAT is used in both the training pipeline and the ablation configuration.',
    aliases: ['Dynamic Advantage Tuning', 'Distribution-aware Training'],
    confidence: 0.71,
    mention_count: 6,
    evidence: [
      { id: 'ev_ctx_003', section: '3.2 Training Pipeline', page: 5, block_id: 'block_3_2_03', kind: 'definition', quote: 'Dynamic Advantage Tuning (DAT) rescales advantage estimates before policy updates.' },
      { id: 'ev_ctx_004', section: 'Appendix B', page: 12, block_id: 'block_b_04', kind: 'usage', quote: 'We additionally report the Distribution-aware Training (DAT) configuration.' },
    ],
    related_terms: ['Advantage estimation', 'Training configuration'],
    review_note: '同一表面词在正文与附录中指向不同概念，不能自动合并。',
  },
  {
    id: 'term_clip_schedule',
    name: 'Adaptive Clip Schedule',
    surface_form: 'adaptive clip schedule',
    type: 'new_term',
    status: 'review_pending',
    definition: '作者用于描述动态裁剪阈值变化过程的论文内术语。',
    author_wording: 'The adaptive clip schedule follows the variance of recent policy updates.',
    aliases: ['clip schedule'],
    confidence: 0.86,
    mention_count: 4,
    evidence: [
      { id: 'ev_ctx_005', section: '3.1 Adaptive Clipping', page: 4, block_id: 'block_3_1_05', kind: 'definition', quote: 'The adaptive clip schedule follows the variance of recent policy updates.' },
    ],
    related_terms: ['AdaClip-X', 'Clipping threshold'],
  },
  {
    id: 'term_benchmark_z',
    name: 'Benchmark-Z',
    surface_form: 'Benchmark-Z',
    type: 'dataset',
    status: 'evidence_ready',
    definition: '论文实验使用的多任务训练稳定性评测集合。',
    author_wording: 'Benchmark-Z contains twelve continuous-control tasks with controlled distribution shifts.',
    aliases: [],
    confidence: 0.91,
    mention_count: 8,
    evidence: [
      { id: 'ev_ctx_006', section: '4.1 Setup', page: 6, block_id: 'block_4_1_02', kind: 'definition', quote: 'Benchmark-Z contains twelve continuous-control tasks with controlled distribution shifts.' },
    ],
    related_terms: ['Continuous control', 'Distribution shift'],
  },
  {
    id: 'term_stability_gain',
    name: 'Stability Gain',
    surface_form: 'stability gain',
    type: 'metric',
    status: 'discovered',
    definition: '疑似本文自定义指标，但尚未定位到完整计算公式。',
    author_wording: 'We report stability gain for every training seed.',
    aliases: [],
    confidence: 0.63,
    mention_count: 3,
    evidence: [
      { id: 'ev_ctx_007', section: '4.3 Results', page: 8, block_id: 'block_4_3_01', kind: 'usage', quote: 'We report stability gain for every training seed.' },
    ],
    related_terms: ['Training stability'],
    review_note: '缺少明确公式或定义段落，当前不可发布。',
  },
]

function contextTaskStatus(run: RunSnapshot): TaskStatus {
  const extraction = run.tasks.find((task) => task.id === 'extract')
  if (!extraction || ['pending', 'queued'].includes(extraction.status)) return 'pending'
  if (extraction.status === 'running') return 'queued'
  if (extraction.status === 'failed' || run.status === 'failed') return 'cancelled'
  return 'completed'
}

export function buildDomainContextArtifact(run: RunSnapshot): DomainContextArtifact {
  const published = run.status === 'published'
  return {
    id: `ctx_${run.document_version_id}`,
    run_id: run.id,
    document_id: run.document_id,
    document_version_id: run.document_version_id,
    document_name: run.document_name,
    status: published ? 'published' : run.status === 'awaiting_review' ? 'review_pending' : 'draft',
    scope: 'document',
    release_version: published ? 1 : null,
    schema_version: 'dataweave.context.v1-preview',
    generated_at: run.finished_at || run.last_activity_at,
    evidence_coverage: 0.8,
    terms: terms.map((term) => ({
      ...term,
      aliases: [...term.aliases],
      evidence: term.evidence.map((evidence) => ({ ...evidence })),
      related_terms: [...term.related_terms],
      status: published && term.status === 'evidence_ready' ? 'published' : term.status,
    })),
  }
}

export function buildDomainContextTask(run: RunSnapshot): TaskNode {
  const status = contextTaskStatus(run)
  const artifact = buildDomainContextArtifact(run)
  const completed = status === 'completed'
  const childStatus: TaskStatus = completed ? 'completed' : status === 'cancelled' ? 'cancelled' : 'pending'
  const metrics = [
    { name: 'context_candidates', label: '上下文候选', value: artifact.terms.length, unit: '个' },
    { name: 'definition_ready', label: '定义证据完整', value: artifact.terms.filter((term) => ['evidence_ready', 'published'].includes(term.status)).length, unit: '个' },
    { name: 'ambiguous', label: '存在歧义', value: artifact.terms.filter((term) => term.status === 'ambiguous').length, unit: '个' },
    { name: 'evidence_coverage', label: '证据覆盖', value: Math.round(artifact.evidence_coverage * 100), unit: '%' },
  ]
  const children: TaskNode[] = [
    ['context_discover', '专有名词与方法发现', 'ContextDiscoveryPreview'],
    ['context_evidence', '定义与原文证据绑定', 'EvidenceLinkerPreview'],
    ['context_resolve', '论文内归一与歧义检查', 'ScopeResolverPreview'],
    ['context_validate', '候选质量校验', 'ContextQualityGatePreview'],
  ].map(([id, name, executor]) => ({
    id,
    name,
    kind: 'domain_context_step',
    description: `${name}的前端演示任务，后端实现可沿用相同 Task 契约。`,
    executor,
    status: childStatus,
    attempt: completed ? 1 : 0,
    max_attempts: 3,
    started_at: completed ? run.started_at : null,
    finished_at: completed ? run.last_activity_at : null,
    duration_ms: completed ? 320 : null,
    input: { source: 'document_json', scope: 'document' },
    output: completed ? { artifact_id: artifact.id } : {},
    metrics: [],
    warnings: [],
    children: [],
    storage_locations: [{ service: 'dataweave', backend: 'frontend_preview', role: 'preview', authoritative: false }],
  }))
  return {
    id: 'domain_context',
    name: '领域上下文提取',
    kind: 'domain_context',
    description: '发现论文中的专有名词、作者命名方法和缩写，绑定定义证据并保留歧义候选。',
    executor: 'ContextCompilerPreview',
    status,
    attempt: completed ? 1 : 0,
    max_attempts: 3,
    started_at: completed ? run.started_at : null,
    finished_at: completed ? run.last_activity_at : null,
    duration_ms: completed ? 1280 : null,
    input: { source: 'dataweave.document.v1', scope: 'document', term_types: ['new_term', 'method', 'acronym'] },
    output: completed ? { artifact_id: artifact.id, terms: artifact.terms, status: artifact.status, schema_version: artifact.schema_version } : {},
    metrics: completed ? metrics : [],
    warnings: [],
    children,
    storage_locations: [{ service: 'dataweave', backend: 'frontend_preview', role: 'preview', authoritative: false }],
  }
}
