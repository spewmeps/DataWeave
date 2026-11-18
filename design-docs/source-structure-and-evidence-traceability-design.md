# DataWeave 论文结构索引与证据溯源设计

## 1. 文档状态

- 状态：待评审
- 范围：目标架构、数据契约与分阶段落地方案
- 基线：当前 FastAPI + SQLite + Local Artifact + Vue，以及 RAGFlow 内容后端边界
- 更新日期：2026-11-18

## 2. 结论

DataWeave 现有设计并非完全缺少结构索引和证据能力，但目前主要停留在目标、页面原型和分散 Issue，尚未形成可执行的底层契约。

已经存在的设计意图包括：

- `document_id` / `document_version_id`、文件 Hash 和解析版本。
- Document JSON、PageIndex、字段 Evidence、领域上下文 Evidence。
- RAGFlow Chunk 引用、页码或坐标定位以及 PDF 高亮。
- Claim / Evidence、Graph / Tree 与证据回溯的产品方向。

当前关键缺口是：

1. Document JSON 没有强制的稳定 `section_id`、`block_id` 和规范化位置契约。
2. Evidence 主要是 `quote + page + section`，没有统一 `evidence_id`、Block Span 和 Locator。
3. 没有 `Chunk ↔ Block` 多对多字符区间映射，Chunk 变化后证据可能失去定位。
4. 没有统一坐标系、页面旋转/CropBox 和解析器坐标转换规范。
5. Claim 还不是可持久化、可核验、可表达支持/反驳/提及关系的领域对象。
6. PDF 定位、高亮和证据支持准确率没有端到端质量门禁。

因此，DataWeave 应将“论文结构索引”正式定义为：

> 以 Source Version 为版本边界，以 Source Block 为稳定证据锚点，以 Chunk 为可重建检索载体，以 Claim 为知识表达，并通过 Locator 将检索与结论追溯到 PDF 原文。

## 3. 与 RAGFlow 的边界

继续遵守既有边界，不在 DataWeave 重复建设 RAGFlow 已拥有的文章存储、通用 Chunk 正文、BM25 和向量索引。

| 能力 | 权威后端 | DataWeave 责任 |
| --- | --- | --- |
| 原始文章、正文、基础 Chunk | RAGFlow | 保存业务身份、版本和远端 ID 映射 |
| 通用关键词、向量和混合检索 | RAGFlow | 调用 Provider API、融合增强候选 |
| Parser 原始输出 | RAGFlow / MinerU 等 Provider | 保存不可变 Artifact 引用、版本和校验信息 |
| Section、Block、Location 规范模型 | DataWeave | 从 Provider 输出归一化，作为证据锚点权威数据 |
| Chunk–Block Span 映射 | DataWeave | 记录远端 Chunk revision 到稳定 Block 的映射 |
| Claim、Evidence、审核和发布 | DataWeave | 管理增强知识、证据关系与不可变 Release |
| PDF 文件读取 | RAGFlow 或 DataWeave Source Gateway | 通过 DataWeave API 代理，前端不持有 RAGFlow Key |

Docling、MinerU、GROBID 或 RAGFlow 的字段只能作为 Provider 输入，不能直接成为跨版本业务主键。DataWeave 应使用 Adapter 将不同 Provider 输出转换成自己的固定 Schema。

## 4. 分层模型

```text
Paper
└─ Source Version                       具体 PDF 版本与 Hash
   ├─ Page                              页面尺寸、旋转与坐标上下文
   ├─ Section Tree                      论文逻辑章节树
   ├─ Source Block                      稳定证据锚点
   │  └─ Block Location [1..n]          页码、BBox、字符区间
   ├─ Retrieval Chunk Ref               RAGFlow Chunk + revision
   │  └─ Chunk Block Span [n..m]        Chunk 与 Block 双向映射
   └─ Evidence                          Block 或局部 Span
      └─ Claim Evidence Relation        SUPPORTS / CONTRADICTS / MENTIONS
         └─ Claim                       带限定条件的知识主张
```

必须明确：

- Section Tree 用于结构导航，不替代精确位置索引。
- Source Block 是稳定证据单位，不以 Chunk 作为证据主键。
- Chunk 是可重新切分的检索产物，必须绑定 Provider revision。
- Evidence 是可核验的原文片段，Claim 是基于证据形成的知识表达。

## 5. 核心数据契约

### 5.1 Paper 与 Source Version

`paper_id` 表示同一学术工作，`source_version_id` 表示某个具体 PDF 版本。

```json
{
  "paper_id": "paper_01",
  "source_version_id": "srcver_02",
  "document_version_id": "ver_02",
  "file_sha256": "...",
  "source_type": "conference_final",
  "provider": "ragflow",
  "provider_document_id": "doc_remote_01",
  "parser": {"name": "mineru", "version": "2.x"},
  "schema_version": "dataweave.source-structure.v1"
}
```

所有 Page、Section、Block、Chunk Map、Evidence 和 Claim 必须最终绑定 `source_version_id`。同标题、同 DOI 不能替代文件版本边界。

### 5.2 Page

每页必须保存坐标转换所需上下文：

| 字段 | 说明 |
| --- | --- |
| `page_id` | DataWeave 稳定 ID |
| `source_version_id` | 所属 PDF 版本 |
| `pdf_page` | 从 1 开始的物理 PDF 页码 |
| `printed_page_label` | 可选的论文印刷页码 |
| `width_pt`, `height_pt` | PDF point 尺寸 |
| `rotation` | 0 / 90 / 180 / 270 |
| `crop_box`, `media_box` | 坐标转换边界 |

### 5.3 Section

```json
{
  "section_id": "sec_method_training",
  "source_version_id": "srcver_02",
  "parent_id": "sec_method",
  "title": "3.2 Training",
  "level": 2,
  "reading_order": 14,
  "first_block_id": "blk_0101",
  "last_block_id": "blk_0119"
}
```

章节树使用 `parent_id` 和排序字段即可；首版不需要为单篇论文引入图数据库。

### 5.4 Source Block

Block 类型至少支持：

- `heading`
- `paragraph`
- `formula`
- `table`
- `figure`
- `caption`
- `list_item`
- `footnote`
- `reference`

```json
{
  "block_id": "blk_0108",
  "source_version_id": "srcver_02",
  "section_id": "sec_method_training",
  "block_type": "paragraph",
  "reading_order": 108,
  "normalized_text": "The proposed training strategy ...",
  "normalized_text_sha256": "...",
  "provider_ref": "#/texts/50",
  "provider_payload_hash": "..."
}
```

`provider_ref` 只用于回看原始解析结果，不保证跨解析版本稳定。`block_id` 应由 Source Version、阅读顺序、类型和内容指纹确定性生成；重解析后若内容或位置发生实质变化，应产生新结构 revision，而不是静默覆盖。

### 5.5 Block Location

一个 Block 可以跨栏、跨页或由多个矩形区域组成，因此位置是 `1..n`：

```json
{
  "location_id": "loc_0201",
  "block_id": "blk_0108",
  "pdf_page": 5,
  "bbox_norm": [0.12, 0.28, 0.78, 0.36],
  "char_start": 0,
  "char_end": 186,
  "coord_origin": "TOPLEFT",
  "provider_bbox": [108.0, 405.1, 504.0, 330.8],
  "provider_coord_origin": "BOTTOMLEFT"
}
```

内部规范：

- `pdf_page` 从 1 开始。
- `bbox_norm` 为 `[left, top, right, bottom]`，左上角原点，范围 `0..1`。
- 字符范围使用半开区间 `[start, end)`。
- 字符偏移基于 `normalized_text` 的 Unicode code point，而不是 UTF-8 byte。
- 同时保存 Provider 原始坐标与坐标原点，便于审计转换误差。
- 页面旋转、CropBox 与 MediaBox 必须参与转换测试。

### 5.6 Retrieval Chunk 与 Chunk–Block Span

DataWeave 不复制通用 Chunk 正文，但保存远端引用、revision 和映射：

```json
{
  "chunk_id": "chunk_remote_08",
  "provider": "ragflow",
  "provider_document_id": "doc_remote_01",
  "chunk_revision": "rev_17",
  "source_version_id": "srcver_02",
  "content_hash": "...",
  "chunk_order": 8
}
```

`chunk_block_span` 必须支持多对多：

| 字段 | 说明 |
| --- | --- |
| `chunk_id`, `chunk_revision` | 远端 Chunk 版本 |
| `block_id` | DataWeave 稳定 Block |
| `chunk_start`, `chunk_end` | Chunk 规范化文本范围 |
| `block_start`, `block_end` | Block 规范化文本范围 |
| `mapping_method` | `parser_native` / `deterministic_alignment` / `fuzzy_backfill` |
| `mapping_confidence` | 0..1 |
| `verification_status` | `verified` / `needs_review` / `stale` |

映射应在 Chunk 生成或同步时建立。历史 Chunk 可使用规范化文本、局部字符对齐和相似度回填，但不能把低置信映射标记为已验证。

### 5.7 Evidence 与 Claim

Evidence 指向 Block 或 Block 内局部 Span：

```json
{
  "evidence_id": "ev_0021",
  "source_version_id": "srcver_02",
  "block_id": "blk_0206",
  "start_offset": 14,
  "end_offset": 92,
  "quote": "...",
  "quote_sha256": "...",
  "locator_ids": ["loc_0311"],
  "verification_status": "verified"
}
```

Claim 必须保留限定条件：

```json
{
  "claim_id": "claim_0008",
  "subject": "Method X",
  "predicate": "OUTPERFORMS",
  "object": "Baseline Y",
  "qualifiers": {
    "dataset": "Dataset D",
    "metric": "success_rate",
    "experimental_setting": "Setting S"
  },
  "status": "candidate"
}
```

Claim 与 Evidence 通过关系表连接，关系只能是：

- `SUPPORTS`
- `CONTRADICTS`
- `MENTIONS`

关系还必须保存 `verification_status`、抽取器版本、审核记录和发布版本。找到相关原文不等于原文支持 Claim。

## 6. 存储模型

建议新增以下 Repository 表或等价对象：

| 对象 | 关键索引 |
| --- | --- |
| `paper_source_versions` | `paper_id`, `file_sha256`, `document_version_id` |
| `source_pages` | `source_version_id`, `pdf_page` |
| `paper_sections` | `source_version_id`, `parent_id`, `reading_order` |
| `source_blocks` | `source_version_id`, `section_id`, `reading_order` |
| `block_locations` | `block_id`, `pdf_page` |
| `retrieval_chunk_refs` | `provider`, `chunk_id`, `chunk_revision` |
| `chunk_block_spans` | `(chunk_id, chunk_revision, block_id)`，并建立 `block_id` 反向索引 |
| `evidence_items` | `source_version_id`, `block_id`, `verification_status` |
| `knowledge_claims` | `status`, `release_id` |
| `claim_evidence_links` | `claim_id`, `evidence_id`, `relation`，并支持反向查询 |

SQLite 继续作为 MVP 元数据存储，通过 Repository 接口保留 PostgreSQL/GaussDB 迁移能力。大体积解析原始文件仍放 Artifact Store；数据库保存稳定标识、定位、映射、状态与 Hash。

## 7. 处理流水线

```text
Source Register
  → Provider Parse
  → Parser Adapter Normalize
  → Page / Section / Block / Location Persist
  → RAGFlow Document & Chunk Sync
  → Chunk–Block Span Build
  → Structure and Locator Validate
  → Claim / Evidence Extract
  → Evidence Support Validate
  → Review
  → Immutable Release
```

### 7.1 Parser Adapter

Adapter 输出统一 `dataweave.source-structure.v1`，至少负责：

- Provider 字段映射。
- 页码与坐标归一化。
- 阅读顺序和章节修复。
- 确定性 ID 与内容 Hash。
- 原始 Provider payload 和转换版本留痕。

首版继续以现有 RAGFlow/MinerU 链路为主。Docling 可作为结构与坐标 POC 对照，GROBID 可作为学术元数据和参考文献增强；是否切换主解析器由评测数据决定，而不是由设计文档预设。

### 7.2 失效传播

以下变化必须使下游对象进入 `STALE`：

- Source Version 改变。
- Parser 或规范化 Schema 版本改变并导致 Block revision 变化。
- RAGFlow Chunk revision 改变。
- Chunk–Block 映射 Hash 改变。
- Evidence 所引用的 Block 或 Quote Hash 不再匹配。

历史 Release 保持不可变，新版本通过重建产生，不原地篡改旧证据。

## 8. API 边界

建议 API：

| API | 用途 |
| --- | --- |
| `GET /api/source-versions/{id}/structure` | 查询 Page、Section Tree 与 Block 摘要 |
| `GET /api/source-versions/{id}/blocks/{block_id}` | 查询 Block、位置和版本 |
| `GET /api/chunks/{chunk_id}/source-spans` | Chunk → Block Span 与 Locator |
| `GET /api/blocks/{block_id}/chunks` | Block → 当前及历史 Chunk 引用 |
| `GET /api/evidence/{evidence_id}` | 获取 Quote、Block、Locator 和版本状态 |
| `GET /api/evidence/{evidence_id}/source` | 由 DataWeave 代理 PDF/页面资源 |
| `GET /api/claims/{claim_id}` | 获取 Claim、限定条件和支持/反驳证据 |

API 不返回服务器绝对路径、RAGFlow Key 或未经授权的 Provider URL。

## 9. 检索到原文的执行链

```text
Question
  → RAGFlow Hybrid Search
  → Chunk ID + revision
  → Chunk–Block Span
  → Source Block
  → Evidence / Claim support check
  → Block Location
  → Source Version PDF
  → PDF.js page jump + BBox highlight
```

降级策略：

1. 有验证过的 BBox：精确高亮。
2. 只有页码和 Quote：跳页并在指定页局部搜索。
3. 只有页码：跳页并提示“无法精确高亮”。
4. Source Version 或 Chunk revision 不匹配：阻止定位并标记证据已失效。

PyMuPDF 文本搜索只能作为历史数据回填或定位降级，不能替代持久化 Block Locator。

## 10. 前端交互

PDF Reader 建议使用 PDF.js，并由 Evidence Drawer 驱动：

- 展示 Paper、Source Version、章节、物理页码和证据状态。
- 点击 Evidence 后跳转页面并将归一化 BBox 转为当前 viewport 坐标。
- 一个 Evidence 可高亮多个矩形或跨页区域。
- 原文 Quote、模型概括和 Claim 分开展示。
- 显示 SUPPORTS / CONTRADICTS / MENTIONS，不把“相关”冒充“支持”。
- 坐标缺失、版本过期或 Provider 不可用时显示明确降级原因。

## 11. 质量门禁与 POC

先选择约 100 篇代表性 PDF，覆盖双栏、复杂公式、跨页表格、扫描件、旋转页和多版本论文。

| 指标 | 定义 | 首轮目标 |
| --- | --- | --- |
| Section Tree 正确率 | 标题层级与页范围正确 | ≥ 95% |
| Block 顺序正确率 | 阅读顺序与原文一致 | ≥ 97% |
| Chunk–Block 映射覆盖率 | 检索 Chunk 可映射到 Block 的字符比例 | ≥ 98% |
| PDF 页码准确率 | Locator 打开正确物理页 | ≥ 99% |
| BBox 高亮 IoU / 命中率 | 高亮覆盖目标原文区域 | 按文档类型分层验收 |
| Evidence Support Precision | 标记 SUPPORTS 的证据确实支持 Claim | ≥ 95% |

必须单独统计文本型、扫描型、双栏、公式和跨页表格，不用总体平均掩盖困难文档失败。

## 12. 分阶段交付

### P0 · 来源结构基础

- 固化 Source Version、Page、Section、Block、Location Schema。
- 实现当前 Parser 输出到统一 Schema 的 Adapter。
- 保存结构 revision、确定性 ID、坐标转换与校验报告。

### P0 · Chunk 映射

- 同步 RAGFlow Chunk ID/revision。
- 建立 Chunk–Block 双向字符 Span。
- 实现 revision 失效传播与历史映射回填。

### P1 · 证据与主张

- 抽取公共 Evidence Store。
- 建立 Claim、Qualifier 和 Claim–Evidence Relation。
- 接入审核、冲突和不可变 Release。

### P1 · 原文联动

- PDF.js 跳页、多矩形和跨页高亮。
- Evidence Drawer 与 Source Locator API。
- 完成坐标一致性 POC 和质量门禁。

## 13. 明确不做

- 不在 DataWeave 再保存一套 RAGFlow 通用 Chunk 正文和向量索引。
- 不把 Provider element ref 当成永久业务 ID。
- 不以 Chunk 作为唯一原文证据单位。
- 不使用模糊文本搜索伪装成已验证的精确映射。
- 不因为找到相关原文就自动将关系标记为 SUPPORTS。
- 不在没有评测结果前强制将主解析器切换为 Docling 或 GROBID。
