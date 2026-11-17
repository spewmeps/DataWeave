# DataWeave 功能与缺陷清单

> 本文件统一记录已实现基线、进行中能力、后续规划和已知缺陷，是 GitHub Issue 的本地事实源。先运行 `python3 scripts/issue_manager.py sync` 预览，确认后再使用 `--apply` 写入 GitHub。

## 状态约定

- `Closed`：当前代码已经实现并具备可验证入口。
- `Open + status:partial`：UI 或契约已经存在，但真实后端链路尚未闭环。
- `Open`：待开发功能、技术债或已知缺陷。
- 已实现 Issue 只描述当前交付边界，后续增强使用新的 Issue。

## 汇总

<!-- issue-index:start -->
| Key | GitHub | 类型 | 优先级 | 模块 | 状态 | 标题 |
| --- | --- | --- | --- | --- | --- | --- |
| `DW-001` | [#1](https://github.com/spewmeps/DataWeave/issues/1) | Feature | P0 | foundation | Closed | 建立 DataWeave 前后端可运行工程 |
| `DW-002` | [#2](https://github.com/spewmeps/DataWeave/issues/2) | Feature | P0 | ingestion | Closed | 实现 PDF 上传、文件保存和哈希重复检测 |
| `DW-003` | [#3](https://github.com/spewmeps/DataWeave/issues/3) | Feature | P0 | frontend | Closed | 实现论文文档列表和运行状态跟踪 |
| `DW-004` | [#4](https://github.com/spewmeps/DataWeave/issues/4) | Feature | P0 | frontend | Closed | 实现论文结构化提取模板配置页面 |
| `DW-005` | [#5](https://github.com/spewmeps/DataWeave/issues/5) | Feature | P0 | backend | Closed | 接入 MinerU 文档解析器和解析产物存储 |
| `DW-006` | [#6](https://github.com/spewmeps/DataWeave/issues/6) | Feature | P0 | backend | Closed | 实现 Schema 驱动的论文结构化字段提取 |
| `DW-007` | [#7](https://github.com/spewmeps/DataWeave/issues/7) | Feature | P0 | runtime | Closed | 实现异步 Run、Task DAG 和 SSE 事件流 |
| `DW-008` | [#8](https://github.com/spewmeps/DataWeave/issues/8) | Feature | P1 | observability | Closed | 实现运行日志、Agent 日志和 Trace 查看 |
| `DW-009` | [#9](https://github.com/spewmeps/DataWeave/issues/9) | Feature | P0 | backend | Closed | 实现上传、运行和事件的 SQLite 持久化 |
| `DW-010` | [#10](https://github.com/spewmeps/DataWeave/issues/10) | Feature | P0 | runtime | Closed | 实现失败运行重新执行和基础发布 |
| `DW-011` | [#11](https://github.com/spewmeps/DataWeave/issues/11) | Feature | P1 | backend | Closed | 实现解析产物查询和文件下载 API |
| `DW-012` | [#12](https://github.com/spewmeps/DataWeave/issues/12) | Feature | P1 | frontend | Closed | 实现知识产物总览和产物类型导航 UI |
| `DW-013` | [#13](https://github.com/spewmeps/DataWeave/issues/13) | Feature | P0 | frontend | Open | 实现解析运行中的领域上下文工作区 UI |
| `DW-014` | [#14](https://github.com/spewmeps/DataWeave/issues/14) | Feature | P0 | frontend | Open | 实现知识产物中的领域上下文资产 UI |
| `DW-015` | [#15](https://github.com/spewmeps/DataWeave/issues/15) | Feature | P1 | tooling | Closed | 实现 Markdown Issue 管理及提交关联脚本 |
| `DW-016` | [#16](https://github.com/spewmeps/DataWeave/issues/16) | Feature | P0 | runtime | Open | 将领域上下文正式接入后端 Task DAG |
| `DW-017` | [#17](https://github.com/spewmeps/DataWeave/issues/17) | Feature | P0 | runtime | Open | 统一运行页、任务树和文档列表进度口径 |
| `DW-018` | [#18](https://github.com/spewmeps/DataWeave/issues/18) | Feature | P1 | runtime | Open | 实现运行取消和指定任务局部重试 |
| `DW-019` | [#19](https://github.com/spewmeps/DataWeave/issues/19) | Feature | P1 | artifacts | Open | 建立统一 Artifact Manifest |
| `DW-020` | [#20](https://github.com/spewmeps/DataWeave/issues/20) | Feature | P0 | backend | Open | 定义领域上下文数据契约和状态机 |
| `DW-021` | [#21](https://github.com/spewmeps/DataWeave/issues/21) | Feature | P0 | backend | Open | 实现论文级专有名词、方法和缩写真实抽取 |
| `DW-022` | [#22](https://github.com/spewmeps/DataWeave/issues/22) | Feature | P0 | backend | Open | 实现定义证据、使用位置和相关概念提取 |
| `DW-023` | [#23](https://github.com/spewmeps/DataWeave/issues/23) | Feature | P0 | backend | Open | 实现领域上下文候选质量校验和空结果处理 |
| `DW-024` | [#24](https://github.com/spewmeps/DataWeave/issues/24) | Feature | P1 | fullstack | Open | 在模板中增加领域上下文配置和运行快照 |
| `DW-025` | [#25](https://github.com/spewmeps/DataWeave/issues/25) | Feature | P0 | backend | Open | 建设 Context Repository |
| `DW-026` | [#26](https://github.com/spewmeps/DataWeave/issues/26) | Feature | P0 | backend | Open | 实现领域上下文候选审核 API 和审计记录 |
| `DW-027` | [#27](https://github.com/spewmeps/DataWeave/issues/27) | Feature | P0 | fullstack | Open | 实现修改后接受和歧义保留 |
| `DW-028` | [#28](https://github.com/spewmeps/DataWeave/issues/28) | Feature | P0 | backend | Open | 实现不可变 Context Release |
| `DW-029` | [#29](https://github.com/spewmeps/DataWeave/issues/29) | Feature | P0 | backend | Open | 实现文档与 Context Release 一致性发布事务 |
| `DW-030` | [#30](https://github.com/spewmeps/DataWeave/issues/30) | Feature | P1 | frontend | Open | 接入 PDF 原文定位和证据高亮 |
| `DW-031` | [#31](https://github.com/spewmeps/DataWeave/issues/31) | Feature | P0 | fullstack | Open | 接通知识产物领域上下文真实 API |
| `DW-032` | [#32](https://github.com/spewmeps/DataWeave/issues/32) | Feature | P1 | backend | Open | 实现真实 PageIndex 知识产物 |
| `DW-033` | [#33](https://github.com/spewmeps/DataWeave/issues/33) | Feature | P1 | backend | Open | 实现 Graph 和 Tree 知识产物 |
| `DW-034` | [#34](https://github.com/spewmeps/DataWeave/issues/34) | Feature | P1 | backend | Open | 实现 DataWeave 增强检索与融合排序产物 |
| `DW-035` | [#35](https://github.com/spewmeps/DataWeave/issues/35) | Feature | P1 | fullstack | Open | 实现单项知识产物重建和失败重试 |
| `DW-036` | [#36](https://github.com/spewmeps/DataWeave/issues/36) | Feature | P1 | backend | Open | 实现术语 Resolve 和歧义解析 |
| `DW-037` | [#37](https://github.com/spewmeps/DataWeave/issues/37) | Feature | P1 | backend | Open | 实现预算化 Context Pack |
| `DW-038` | [#38](https://github.com/spewmeps/DataWeave/issues/38) | Feature | P1 | backend | Open | 将领域上下文接入检索路由 |
| `DW-039` | [#39](https://github.com/spewmeps/DataWeave/issues/39) | Feature | P1 | backend | Open | 实现查询扩展和受控别名 |
| `DW-040` | [#40](https://github.com/spewmeps/DataWeave/issues/40) | Feature | P1 | fullstack | Open | 建立 Context A/B 评估工作台 |
| `DW-041` | [#41](https://github.com/spewmeps/DataWeave/issues/41) | Tech Debt | P1 | frontend | Open | 补齐前端 Vitest 和领域上下文组件测试 |
| `DW-042` | [#42](https://github.com/spewmeps/DataWeave/issues/42) | Tech Debt | P1 | backend | Open | 建立数据库迁移机制 |
| `DW-043` | [#43](https://github.com/spewmeps/DataWeave/issues/43) | Tech Debt | P1 | fullstack | Open | 使用 OpenAPI 生成前端 TypeScript Client |
| `DW-044` | [#44](https://github.com/spewmeps/DataWeave/issues/44) | Tech Debt | P1 | devops | Open | 建立 CI 类型检查、后端测试和前端构建门禁 |
| `DW-045` | [#45](https://github.com/spewmeps/DataWeave/issues/45) | Tech Debt | P2 | observability | Open | 建立运行、发布和检索可观测指标 |
| `DW-051` | [#51](https://github.com/spewmeps/DataWeave/issues/51) | Feature | P0 | backend | Open | 建立可配置的 RAGFlow v1 Provider Adapter |
| `DW-052` | [#52](https://github.com/spewmeps/DataWeave/issues/52) | Feature | P0 | ingestion | Open | 实现 DataWeave 到 RAGFlow 的文档同步与双向映射 |
| `DW-053` | [#53](https://github.com/spewmeps/DataWeave/issues/53) | Feature | P0 | runtime | Open | 将生产解析 DAG 切换为 RAGFlow Chunk 来源 |
| `DW-054` | [#54](https://github.com/spewmeps/DataWeave/issues/54) | Feature | P0 | backend | Open | 建立 RAGFlow 对账、漂移检测与删除 Saga |
| `DW-055` | [#55](https://github.com/spewmeps/DataWeave/issues/55) | Feature | P0 | backend | Open | 实现 RAGFlow 基础检索网关和权限过滤 |
| `DW-056` | [#56](https://github.com/spewmeps/DataWeave/issues/56) | Feature | P1 | backend | Open | 实现 DataWeave 统一 Chat Completion 与可选 RAGFlow Chat 模式 |
| `DW-057` | [#57](https://github.com/spewmeps/DataWeave/issues/57) | Feature | P0 | fullstack | Open | 实现前端知识库配置与数据位置标记 |
| `DW-046` | [#46](https://github.com/spewmeps/DataWeave/issues/46) | Bug | P1 | frontend | Open | 修复领域上下文预览任务与后端运行进度不一致 |
| `DW-047` | [#47](https://github.com/spewmeps/DataWeave/issues/47) | Bug | P1 | fullstack | Open | 修复模板配置仅保存在浏览器导致跨设备丢失 |
| `DW-048` | [#48](https://github.com/spewmeps/DataWeave/issues/48) | Bug | P1 | fullstack | Open | 修复领域上下文审核刷新后状态丢失 |
| `DW-049` | [#49](https://github.com/spewmeps/DataWeave/issues/49) | Bug | P2 | frontend | Open | 修复知识产物卡片将任务完成误认为正式产物可用 |
| `DW-050` | [#50](https://github.com/spewmeps/DataWeave/issues/50) | Bug | P2 | backend | Open | 修复已发布状态缺少 Artifact Release 一致性校验 |
<!-- issue-index:end -->

# M0 · 已实现产品基线

## [DW-001] 建立 DataWeave 前后端可运行工程
<!-- issue: number=1; state=closed; labels=enhancement,priority:P0,area:foundation,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- Vue 3 + TypeScript + Vite 前端、FastAPI 后端、SQLite 本地存储。
- 一键启动、停止、重启、状态检查、健康检查和服务日志。
### 验收标准
- [x] 前后端可一键启动，`/api/health` 返回正常。
<!-- /issue-body -->

---

## [DW-002] 实现 PDF 上传、文件保存和哈希重复检测
<!-- issue: number=2; state=closed; labels=enhancement,priority:P0,area:ingestion,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- PDF 类型和 50 MB 限制、SHA-256、原始文件持久化及重复标记。
- 建立 Upload、Document、Document Version 标识。
### 验收标准
- [x] 合法 PDF 可保存，非法文件有明确错误，相同内容可识别。
<!-- /issue-body -->

---

## [DW-003] 实现论文文档列表和运行状态跟踪
<!-- issue: number=3; state=closed; labels=enhancement,priority:P0,area:frontend,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- 文档列表、搜索、刷新、运行状态、当前任务和进度。
- 支持进入运行详情及重新执行文档。
### 验收标准
- [x] 上传文档和最新运行可查询并进入详情。
<!-- /issue-body -->

---

## [DW-004] 实现论文结构化提取模板配置页面
<!-- issue: number=4; state=closed; labels=enhancement,priority:P0,area:frontend,templates,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- 内置论文模板 v3、字段选择、必选字段保护、自定义模板和存储目标配置。
- 当前自定义配置保存于浏览器 localStorage。
### 验收标准
- [x] 用户可配置字段和产物目标，必选字段受保护。
<!-- /issue-body -->

---

## [DW-005] 接入 MinerU 文档解析器和解析产物存储
<!-- issue: number=5; state=closed; labels=enhancement,priority:P0,area:backend,parser,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- MinerU Mock/Remote Transport，以及提交、等待、保存三个解析子任务。
- 保存 Markdown、Middle JSON、Structured Content 和图片。
### 验收标准
- [x] Mock 链路稳定完成，产物写入 Artifact Store 并登记 SQLite。
<!-- /issue-body -->

---

## [DW-006] 实现 Schema 驱动的论文结构化字段提取
<!-- issue: number=6; state=closed; labels=enhancement,priority:P0,area:backend,extraction,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- Metadata、Research、Method、Experiment Agent 分组抽取和 Schema Merge。
- 提供 Mock 与 DeepAgents Extractor，输出字段、证据和执行信息。
### 验收标准
- [x] 可按模板启用字段抽取，生产失败不静默回退 Mock。
<!-- /issue-body -->

---

## [DW-007] 实现异步 Run、Task DAG 和 SSE 事件流
<!-- issue: number=7; state=closed; labels=enhancement,priority:P0,area:runtime,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- Run Snapshot、多层 Task DAG、状态流转、进度和 SSE。
- 活动运行冲突保护，失败后结算未执行任务。
### 验收标准
- [x] 运行可持续查询，同文档版本活动冲突返回 409。
<!-- /issue-body -->

---

## [DW-008] 实现运行日志、Agent 日志和 Trace 查看
<!-- issue: number=8; state=closed; labels=enhancement,priority:P1,area:observability,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- Run/Agent NDJSON 日志、Agent Trace API。
- 运行详情支持概览、输入、输出、指标、Raw 和失败原因。
### 验收标准
- [x] 日志与 Trace 可按 Run/Agent 查询，不存在对象返回 404。
<!-- /issue-body -->

---

## [DW-009] 实现上传、运行和事件的 SQLite 持久化
<!-- issue: number=9; state=closed; labels=enhancement,priority:P0,area:backend,persistence,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- 持久化上传、Run Snapshot、请求和事件序列。
- 重启恢复历史，并将执行中任务收敛为中断失败。
### 验收标准
- [x] 服务重启后历史可读且不会残留虚假运行中状态。
<!-- /issue-body -->

---

## [DW-010] 实现失败运行重新执行和基础发布
<!-- issue: number=10; state=closed; labels=enhancement,priority:P0,area:runtime,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- Retry Run、来源运行和重试次数记录。
- 完成运行可切换 Published；当前不代表正式 Artifact 原子发布。
### 验收标准
- [x] 新重试运行可追溯原运行，完成运行可执行基础发布。
<!-- /issue-body -->

---

## [DW-011] 实现解析产物查询和文件下载 API
<!-- issue: number=11; state=closed; labels=enhancement,priority:P1,area:backend,artifacts,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- 按运行/产物查询，下载 Markdown、Middle JSON 和 Structured Content。
- 返回解析器版本、状态、进度、元数据和文件 URL。
### 验收标准
- [x] 解析产物可关联运行与文档版本并读取。
<!-- /issue-body -->

---

## [DW-012] 实现知识产物总览和产物类型导航 UI
<!-- issue: number=12; state=closed; labels=enhancement,priority:P1,area:frontend,artifacts,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- 文档级产物总览，以及 PageIndex、Graph、Tree、Hybrid、领域上下文导航。
- 当前交付为总览和导航框架，不代表各产物均已真实物化。
### 验收标准
- [x] 有运行记录的文档可查看产物状态并返回来源运行。
<!-- /issue-body -->

---

## [DW-013] 实现解析运行中的领域上下文工作区 UI
<!-- issue: number=13; state=open; labels=enhancement,priority:P0,area:frontend,domain-context,status:partial; assignees= -->
<!-- issue-body -->
### 已完成
- 任务组、摘要、候选列表、筛选、详情、证据、接受/排除和空/失败状态 UI。
### 待闭环
- [ ] 替换前端演示数据，接入真实 Task、候选、持久化审核和 PDF 定位。
### 完成条件
- [ ] 刷新后结果一致且不依赖 `domainContextDemo.ts`。
<!-- /issue-body -->

---

## [DW-014] 实现知识产物中的领域上下文资产 UI
<!-- issue: number=14; state=open; labels=enhancement,priority:P0,area:frontend,domain-context,artifacts,status:partial; assignees= -->
<!-- issue-body -->
### 已完成
- 领域上下文资产入口、统计、术语列表、详情、证据覆盖率和 Release 展示结构。
### 待闭环
- [ ] 接入 Context Repository、真实 Artifact API、历史 Release 和发布事务。
### 完成条件
- [ ] 页面只展示可追溯到文档版本和运行的真实资产。
<!-- /issue-body -->

---

## [DW-015] 实现 Markdown Issue 管理及提交关联脚本
<!-- issue: number=15; state=closed; labels=enhancement,priority:P1,area:tooling,baseline; assignees= -->
<!-- issue-body -->
### 已实现
- Markdown 格式检查、索引、远端列表、同步预览和显式写入。
- 提交支持 `Refs #N`、`Closes #N` 和多个 Issue。
### 验收标准
- [x] 默认不写 GitHub，`--apply` 才同步远端。
<!-- /issue-body -->

# M1 · 运行体系补齐

## [DW-016] 将领域上下文正式接入后端 Task DAG
<!-- issue: number=16; state=open; labels=enhancement,priority:P0,area:runtime,domain-context; assignees= -->
<!-- issue-body -->
### 范围
- 在 Document JSON/Schema Extraction 后增加发现、证据校验、归并和产物准备任务。
### 验收标准
- [ ] Run Snapshot 返回真实 Context Task；失败可局部重试，历史运行兼容。
<!-- /issue-body -->

---

## [DW-017] 统一运行页、任务树和文档列表进度口径
<!-- issue: number=17; state=open; labels=enhancement,priority:P0,area:runtime,progress; assignees= -->
<!-- issue-body -->
### 范围
- 全部页面使用同一后端 Task DAG，统一父子任务、跳过和部分失败规则。
### 验收标准
- [ ] 三处进度一致，SSE 不倒退且不超过 100%，算法有测试。
<!-- /issue-body -->

---

## [DW-018] 实现运行取消和指定任务局部重试
<!-- issue: number=18; state=open; labels=enhancement,priority:P1,area:runtime,retry; assignees= -->
<!-- issue-body -->
### 范围
- 取消活动运行；仅重试 RAGFlow 同步/解析、Schema Extraction 或 Context；复用有效远端文档、Chunk revision 和本地上游。
### 验收标准
- [ ] 操作幂等，远端解析不会重复创建文档，产物复用/重建血缘可查询。
<!-- /issue-body -->

---

## [DW-019] 建立统一 Artifact Manifest
<!-- issue: number=19; state=open; labels=enhancement,priority:P1,area:artifacts,architecture; assignees= -->
<!-- issue-body -->
### 范围
- 统一记录各产物状态、输入、配置、依赖、校验、位置和 Draft/Published 属性；输入版本包含 RAGFlow document/chunk revision，但对普通客户端只暴露 DataWeave ID。
### 验收标准
- [ ] 所有产物可查询、可判定失效并可回溯运行、DataWeave 版本和远端内容 revision。
<!-- /issue-body -->

# M2 · 领域上下文发现

## [DW-020] 定义领域上下文数据契约和状态机
<!-- issue: number=20; state=open; labels=enhancement,priority:P0,area:backend,domain-context,contract; assignees= -->
<!-- issue-body -->
### 范围
- 定义 Term、Definition、Mention、Evidence、Relation、Review、Release DTO 和状态转换。
### 验收标准
- [ ] OpenAPI 契约完整；非法转换被拒绝；原文、模型摘要、人工修订分离。
<!-- /issue-body -->

---

## [DW-021] 实现论文级专有名词、方法和缩写真实抽取
<!-- issue: number=21; state=open; labels=enhancement,priority:P0,area:backend,domain-context,extraction; assignees= -->
<!-- issue-body -->
### 范围
- 从 RAGFlow Chunk 编译的运行时 Document JSON 提取规范名、原文写法、类型、定义、置信度、次数和相关概念；不持久化第二份通用 Chunk 正文。
### 验收标准
- [ ] 不再依赖演示数据；零候选成功；重跑不重复；不宣称领域原创性。
<!-- /issue-body -->

---

## [DW-022] 实现定义证据、使用位置和相关概念提取
<!-- issue: number=22; state=open; labels=enhancement,priority:P0,area:backend,domain-context,evidence; assignees= -->
<!-- issue-body -->
### 范围
- 区分定义证据与 Mention，保存 section、page、block、quote hash、坐标、RAGFlow chunk 引用和关系证据。
### 验收标准
- [ ] 每个可发布定义有证据，Locator 绑定准确文档版本和 chunk revision；远端重解析后旧证据进入 STALE。
<!-- /issue-body -->

---

## [DW-023] 实现领域上下文候选质量校验和空结果处理
<!-- issue: number=23; state=open; labels=enhancement,priority:P0,area:backend,domain-context,validation; assignees= -->
<!-- issue-body -->
### 范围
- 校验类型、定义、证据、重复和缩写歧义，输出阻断错误与提示。
### 验收标准
- [ ] 零候选为成功；无定义证据不可发布；质量报告可查询。
<!-- /issue-body -->

---

## [DW-024] 在模板中增加领域上下文配置和运行快照
<!-- issue: number=24; state=open; labels=enhancement,priority:P1,area:fullstack,templates,domain-context; assignees= -->
<!-- issue-body -->
### 范围
- 内置能力卡配置术语、方法、缩写及可选数据集/指标，并固化模板和运行版本。
### 验收标准
- [ ] 类型可配置，证据要求强制开启，历史运行显示真实快照。
<!-- /issue-body -->

# M3 · 审核与发布

## [DW-025] 建设 Context Repository
<!-- issue: number=25; state=open; labels=enhancement,priority:P0,area:backend,domain-context,persistence; assignees= -->
<!-- issue-body -->
### 范围
- 通过 Repository 持久化领域对象，建立唯一约束、幂等写入和文档版本索引。
### 验收标准
- [ ] 重启不丢数据，重复落库不重复，Domain 不依赖 FastAPI/具体数据库。
<!-- /issue-body -->

---

## [DW-026] 实现领域上下文候选审核 API 和审计记录
<!-- issue: number=26; state=open; labels=enhancement,priority:P0,area:backend,domain-context,review; assignees= -->
<!-- issue-body -->
### 范围
- 候选查询、接受/排除命令、审核人/原因/时间及幂等键、不可覆盖审计。
### 验收标准
- [ ] 刷新状态不丢，重复命令不重复执行，审计可追溯。
<!-- /issue-body -->

---

## [DW-027] 实现修改后接受和歧义保留
<!-- issue: number=27; state=open; labels=enhancement,priority:P0,area:fullstack,domain-context,review; assignees= -->
<!-- issue-body -->
### 范围
- 修改名称、定义、类型、别名后接受；保存 before/after；保留多个释义。
### 验收标准
- [ ] 不覆盖模型原始结果，歧义不被静默转成唯一术语。
<!-- /issue-body -->

---

## [DW-028] 实现不可变 Context Release
<!-- issue: number=28; state=open; labels=enhancement,priority:P0,area:backend,domain-context,release; assignees= -->
<!-- issue-body -->
### 范围
- 发布论文级不可变 Release，使用 base_release_id 控制并发并支持历史查询。
### 验收标准
- [ ] 历史不可原地修改，并发不覆盖，可回溯文档、审核和证据。
<!-- /issue-body -->

---

## [DW-029] 实现文档与 Context Release 一致性发布事务
<!-- issue: number=29; state=open; labels=enhancement,priority:P0,area:backend,artifacts,domain-context,release; assignees= -->
<!-- issue-body -->
### 范围
- 同一提交边界发布 Context Release 和引用它的 Manifest；未审核项保留 Draft。
### 验收标准
- [ ] 失败不切换当前指针，无半发布状态，页面提示未发布候选数。
<!-- /issue-body -->

---

## [DW-030] 接入 PDF 原文定位和证据高亮
<!-- issue: number=30; state=open; labels=enhancement,priority:P1,area:frontend,evidence,pdf; assignees= -->
<!-- issue-body -->
### 范围
- PDF Viewer 通过 DataWeave API 获取 RAGFlow 文章/Chunk，按页码或坐标定位定义和 Mention，缺坐标时降级为页码加 Quote；前端不得持有 RAGFlow Key。
### 验收标准
- [ ] 可准确核对原文，文档版本或 chunk revision 不匹配时阻止错误定位；RAGFlow 不可用时明确显示原文暂不可取。
<!-- /issue-body -->

# M4 · 知识产物

## [DW-031] 接通知识产物领域上下文真实 API
<!-- issue: number=31; state=open; labels=enhancement,priority:P0,area:fullstack,artifacts,domain-context; assignees= -->
<!-- issue-body -->
### 范围
- 获取 Manifest、Context Artifact、统计、列表、详情、筛选和历史 Release。
### 验收标准
- [ ] 页面只显示后端真实数据，未审核项不进入 Published。
<!-- /issue-body -->

---

## [DW-032] 实现真实 PageIndex 知识产物
<!-- issue: number=32; state=open; labels=enhancement,priority:P1,area:backend,artifacts,page-index; assignees= -->
<!-- issue-body -->
### 范围
- 基于 RAGFlow Chunk 与位置信息构建章节、页面、Block 层级，保存 DataWeave 稳定 ID、远端引用、文本范围、位置和版本。
### 验收标准
- [ ] 可从层级导航到原文，同输入稳定重建并记录构建器版本。
<!-- /issue-body -->

---

## [DW-033] 实现 Graph 和 Tree 知识产物
<!-- issue: number=33; state=open; labels=enhancement,priority:P1,area:backend,artifacts,graph,tree; assignees= -->
<!-- issue-body -->
### 范围
- Graph 保存证据关系，Tree 保存层级；正式语义产物绑定 context_release_id。
### 验收标准
- [ ] 节点/关系可回溯，Draft 不冒充发布产物，版本变化可识别影响。
<!-- /issue-body -->

---

## [DW-034] 实现 DataWeave 增强检索与融合排序产物
<!-- issue: number=34; state=open; labels=enhancement,priority:P1,area:backend,artifacts,retrieval; assignees= -->
<!-- issue-body -->
### 背景
- 文章、Chunk、通用关键词和向量基础索引由 RAGFlow 管理；DataWeave 不再维护第二套通用 Embedding/全文索引。
### 范围
- 建立结构化字段、精确标识符、受控别名、Graph、Topic、Domain Context 和审核状态的本地增强召回。
- 将 RAGFlow `similarity/term_similarity/vector_similarity` 与本地增强特征归一化，按有版本的融合策略执行去重、每篇配额和业务重排。
- 输出统一 DataWeave 文档 ID、Citation、各路分值和排序解释。
### 验收标准
- [ ] 不生成第二套通用 Chunk/Embedding；结果可定位 RAGFlow 原文并按论文/版本聚合。
- [ ] 融合策略、输入候选、分值归一化和最终排序原因可追溯；本地增强失败时可降级到基础检索并显式标记。
- [ ] 离线测试覆盖去重、权限过滤、同论文配额、STALE 证据排除和稳定排序。
<!-- /issue-body -->

---

## [DW-035] 实现单项知识产物重建和失败重试
<!-- issue: number=35; state=open; labels=enhancement,priority:P1,area:fullstack,artifacts,retry; assignees= -->
<!-- issue-body -->
### 范围
- 按 Manifest 单独重建产物，复用有效 RAGFlow 文档与 chunk revision，记录原因、血缘和版本。
### 验收标准
- [ ] 单项失败无需整篇重跑，成功后新版本切换且并发受保护。
<!-- /issue-body -->

# M5 · 智能检索消费

## [DW-036] 实现术语 Resolve 和歧义解析
<!-- issue: number=36; state=open; labels=enhancement,priority:P1,area:backend,domain-context,retrieval; assignees= -->
<!-- issue-body -->
### 范围
- 按查询、文档范围和 Release 返回 unique、ambiguous、not_found。
### 验收标准
- [ ] 返回定义和证据，同名不同义不自动合并，只消费已发布版本。
<!-- /issue-body -->

---

## [DW-037] 实现预算化 Context Pack
<!-- issue: number=37; state=open; labels=enhancement,priority:P1,area:backend,domain-context,retrieval; assignees= -->
<!-- issue-body -->
### 范围
- 按任务和 Token 预算组装定义、别名、禁止合并项和最小证据。
### 验收标准
- [ ] 不超预算、可复现，记录 Release、裁剪原因和 Pack Hash。
<!-- /issue-body -->

---

## [DW-038] 将领域上下文接入检索路由
<!-- issue: number=38; state=open; labels=enhancement,priority:P1,area:backend,retrieval,domain-context; assignees= -->
<!-- issue-body -->
### 范围
- Intent Analyzer 调用 Resolve，Query Engine 选择 SQL、RAGFlow 基础检索、PageIndex、Graph 和 DataWeave 增强融合路径。
### 验收标准
- [ ] 路由可解释，Context 可关闭并回退 RAGFlow 基础检索，增强解析失败不拖垮查询。
<!-- /issue-body -->

---

## [DW-039] 实现查询扩展和受控别名
<!-- issue: number=39; state=open; labels=enhancement,priority:P1,area:backend,retrieval,domain-context; assignees= -->
<!-- issue-body -->
### 范围
- 使用已发布别名和定义特征扩展查询，将原查询、扩展查询及 DataWeave 权限范围传给 RAGFlow Retrieval Adapter，并保留扩展来源。
### 验收标准
- [ ] 扩展可追溯，未解歧义不自动扩展，前后召回可比较。
<!-- /issue-body -->

---

## [DW-040] 建立 Context A/B 评估工作台
<!-- issue: number=40; state=open; labels=enhancement,priority:P1,area:fullstack,evaluation,retrieval; assignees= -->
<!-- issue-body -->
### 范围
- 比较启用/关闭 Context 的 Recall@K、证据命中、回答支持和 Token 成本。
### 验收标准
- [ ] 评测可复现、可下钻，Context 收益与成本可量化。
<!-- /issue-body -->

# M6 · 工程质量

## [DW-041] 补齐前端 Vitest 和领域上下文组件测试
<!-- issue: number=41; state=open; labels=tech-debt,priority:P1,area:frontend,testing; assignees= -->
<!-- issue-body -->
### 范围
- 配置 Vitest/Vue Test Utils，覆盖筛选、详情、审核、空状态和发布状态。
### 验收标准
- [ ] 全新安装后 npm test 可运行，关键交互测试稳定。
<!-- /issue-body -->

---

## [DW-042] 建立数据库迁移机制
<!-- issue: number=42; state=open; labels=tech-debt,priority:P1,area:backend,database; assignees= -->
<!-- issue-body -->
### 范围
- 为状态库、解析产物库和 Context 库建立可重复迁移及版本检查。
### 验收标准
- [ ] 空库可升到最新，已有数据不丢，启动检测不兼容版本。
<!-- /issue-body -->

---

## [DW-043] 使用 OpenAPI 生成前端 TypeScript Client
<!-- issue: number=43; state=open; labels=tech-debt,priority:P1,area:fullstack,api; assignees= -->
<!-- issue-body -->
### 范围
- 从 FastAPI OpenAPI 生成 DTO/Client，并在 CI 检测契约漂移。
### 验收标准
- [ ] 核心 API 使用生成类型，过程可复现且无需手改产物。
<!-- /issue-body -->

---

## [DW-044] 建立 CI 类型检查、后端测试和前端构建门禁
<!-- issue: number=44; state=open; labels=tech-debt,priority:P1,area:devops,ci,testing; assignees= -->
<!-- issue-body -->
### 范围
- CI 执行后端测试、前端类型检查、组件测试和生产构建。
### 验收标准
- [ ] PR 自动检查，失败阻止合并，本地有等价一键命令。
<!-- /issue-body -->

---

## [DW-045] 建立运行、发布和检索可观测指标
<!-- issue: number=45; state=open; labels=tech-debt,priority:P2,area:observability,metrics; assignees= -->
<!-- issue-body -->
### 范围
- 任务耗时/失败/重试/成本、发布与证据质量、RAGFlow 调用延迟/错误码/候选数、检索路由/融合/降级/Pack 指标。
### 验收标准
- [ ] 指标可按运行、版本和 provider 关联且不泄露 API Key、完整 Prompt 或敏感原文。
<!-- /issue-body -->

# M7 · RAGFlow 内容面集成与增强检索底座

## [DW-051] 建立可配置的 RAGFlow v1 Provider Adapter
<!-- issue: number=51; state=open; labels=enhancement,priority:P0,area:backend,ragflow,integration,security; assignees= -->
<!-- issue-body -->
### 背景
- DataWeave 必须通过稳定端口复用 RAGFlow，不能让 RAGFlow HTTP DTO、URL 或凭据渗透到领域层和前端。
### 范围
- 定义 `RagContentProvider`，覆盖上传、解析、状态、Chunk、检索、删除和可选 Chat Completion。
- 实现 `ragflow-v1` Adapter，统一 Bearer 鉴权、HTTP/业务 code、分页、SSE、超时、限流、重试和响应 DTO。
- Provider、base URL、超时、重试、熔断与 credential ref 可配置；API Key 仅从环境或 Secret Manager 获取。
- 增加健康检查和 Mock/契约测试，不调用已移除的 `chats_openai` 路径。
### 验收标准
- [ ] 领域服务和前端不包含 RAGFlow URL、Key 或原始 DTO；可用 Fake Provider 运行单元测试。
- [ ] Chat 使用 RAGFlow 1.0 `/api/v1/openai/{chat_id}/chat/completions`，流式响应正确处理 `[DONE]`。
- [ ] 日志、Task Payload、异常和 Trace 不泄露 Key；429/5xx/超时按策略处理，非幂等操作不盲目重试。
### 非目标
- 本 Issue 不实现业务入库编排和增强融合排序。
<!-- /issue-body -->

---

## [DW-052] 实现 DataWeave 到 RAGFlow 的文档同步与双向映射
<!-- issue: number=52; state=open; labels=enhancement,priority:P0,area:ingestion,ragflow,integration,persistence; assignees= -->
<!-- issue-body -->
### 范围
- 建立 Provider/Dataset Router 和 `rag_document_mapping`，保存 DataWeave 文档版本、RAGFlow dataset/document ID、Hash、同步/解析状态和 revision。
- 上传时 DataWeave 保存业务元数据与带 TTL 暂存文件，将文章权威副本上传 RAGFlow，并写入 `dw_document_id`、`dw_version_id`、`content_sha256` 反向元数据。
- 对外 API 只返回 DataWeave ID；同一版本重复请求通过幂等键和 Hash 复用现有映射。
- 提供同步状态查询，区分 PENDING、UPLOADING、PARSING、ACTIVE、FAILED 和 DELETE_PENDING。
### 验收标准
- [ ] 上传成功后可从 DataWeave 版本查到唯一远端映射，响应丢失重试不会创建重复文档。
- [ ] RAGFlow 达到 DONE 且映射 ACTIVE 前，文档不能发布或进入可检索集合。
- [ ] DataWeave 不长期保存文章二进制/完整正文，暂存文件按 TTL 清理；失败时保留可恢复状态。
- [ ] dataset 路由可按租户/知识域配置，业务代码没有硬编码 dataset ID。
### 依赖
- DW-051、DW-042。
<!-- /issue-body -->

---

## [DW-053] 将生产解析 DAG 切换为 RAGFlow Chunk 来源
<!-- issue: number=53; state=open; labels=enhancement,priority:P0,area:runtime,ragflow,integration,parser; assignees= -->
<!-- issue-body -->
### 范围
- 在 Task DAG 中实现“同步文章 → 触发/等待 RAGFlow 解析 → 分页读取 Chunk → 编译运行时 Document JSON”。
- 保存 `remote_chunk_revision`，下游 Schema Extraction、PageIndex 和 Domain Context 绑定该 revision。
- RAGFlow 作为生产默认正文来源；MinerU 保留为测试/兼容 Adapter，不与 RAGFlow 同时充当生产事实源。
- 更新任务树、SSE、进度和失败分类，支持对远端解析任务安全重试。
### 验收标准
- [ ] 真实运行可仅依赖 RAGFlow 文档/Chunk 完成结构化抽取，不要求本地 MinerU 产物存在。
- [ ] RAGFlow Chunk 分页完整、顺序确定且可回溯 document/chunk ID；不长期复制通用 Chunk 正文。
- [ ] 同一 revision 重跑结果幂等；revision 变化会使依赖产物和 Evidence 进入 STALE。
- [ ] Mock Provider、解析失败、超时、空 Chunk、分页和重启恢复均有测试。
### 依赖
- DW-051、DW-052、DW-017、DW-018。
<!-- /issue-body -->

---

## [DW-054] 建立 RAGFlow 对账、漂移检测与删除 Saga
<!-- issue: number=54; state=open; labels=enhancement,priority:P0,area:backend,ragflow,integration,reliability; assignees= -->
<!-- issue-body -->
### 范围
- Reconciler 对比本地映射和 RAGFlow 文档状态，识别本地无远端、远端孤儿、Hash/解析状态/revision 漂移。
- RAGFlow 重解析后将旧 Evidence 和增强 Artifact 标记 STALE，并触发可控重建。
- 删除先进入 `DELETE_PENDING` 并在检索网关屏蔽，再删除远端文档，成功后关闭映射；失败进入补偿队列。
- 提供管理员对账报告和幂等恢复 API；孤儿删除遵循显式策略，不默认破坏性清理。
### 验收标准
- [ ] 对账可重复执行且不会制造重复文档或误删有效文档。
- [ ] 删除远端失败时内容不会继续通过 DataWeave 被检索，补偿成功后状态最终一致。
- [ ] revision 漂移不会静默复用旧 Citation；对账结果、修复动作和错误可审计。
- [ ] 自动修复仅覆盖确定性场景，孤儿删除需要配置或审批。
### 依赖
- DW-052、DW-019、DW-035。
<!-- /issue-body -->

---

## [DW-055] 实现 RAGFlow 基础检索网关和权限过滤
<!-- issue: number=55; state=open; labels=enhancement,priority:P0,area:backend,ragflow,retrieval,security; assignees= -->
<!-- issue-body -->
### 范围
- DataWeave `/api/retrieval` 调用 RAGFlow `POST /api/v1/retrieval`，支持 dataset/document 范围、metadata_condition、阈值、关键词/向量权重、KNN、重排和高亮配置。
- 将 DataWeave 权限先转换为允许的远端 document IDs/可信过滤条件，远端返回后再次授权校验。
- 将远端结果规范化为 DataWeave 文档版本、Chunk Citation、原始分值和诊断信息。
- 实现超时、熔断和降级响应；管理员可查看脱敏远端诊断，普通客户端不依赖 RAGFlow ID。
### 验收标准
- [ ] 无权限文档在请求过滤和响应过滤两层都不会泄露，包含总数、聚合和高亮内容。
- [ ] RAGFlow 的 similarity、term_similarity 和 vector_similarity 原样保留，不误当作同一尺度相加。
- [ ] 参数有边界校验和版本化默认值；超时/业务错误返回稳定 DataWeave 错误契约。
- [ ] 使用 Fake Provider 完成契约测试，并有可选的本机 RAGFlow 集成测试。
### 依赖
- DW-051、DW-052。
<!-- /issue-body -->

---

## [DW-056] 实现 DataWeave 统一 Chat Completion 与可选 RAGFlow Chat 模式
<!-- issue: number=56; state=open; labels=enhancement,priority:P1,area:backend,ragflow,retrieval,api; assignees= -->
<!-- issue-body -->
### 范围
- 提供 DataWeave `/api/chat/completions`，支持 `dataweave_orchestrated` 默认模式和 `ragflow_chat` 可选模式。
- 默认模式消费 DW-055 与 DW-034 的融合候选，统一组装上下文、回答和 Citation。
- 可选模式调用 `/api/v1/openai/{chat_id}/chat/completions`，启用 reference/reference_metadata 和权限元数据过滤，并校验远端引用映射。
- 正确代理 SSE、取消、客户端断开、usage 和不完整回答状态；`chat_id` 与 dataset 路由分别配置。
### 验收标准
- [ ] 前端只调用 DataWeave 且不接触 RAGFlow Key/chat ID；非流式和流式契约有测试。
- [ ] 默认增强模式不依赖 RAGFlow Chat Assistant；可选模式关闭后基础/增强检索仍可用。
- [ ] 所有 Citation 映射回 DataWeave 文档版本并通过权限与 revision 校验，未知/过期引用不输出为有效证据。
- [ ] SSE 中断不自动重放生成；请求、Token 使用和降级原因可追踪但日志不记录完整敏感 Prompt。
### 依赖
- DW-034、DW-055。
<!-- /issue-body -->

---

## [DW-057] 实现前端知识库配置与数据位置标记
<!-- issue: number=57; state=open; labels=enhancement,priority:P0,area:fullstack,ragflow,integration,settings; assignees= -->
<!-- issue-body -->
### 背景
- 用户需要从 DataWeave 左侧设置入口配置 RAGFlow，而不是修改服务器文件；同时所有核心数据都必须明确显示实际存储后端。
### 范围
- 左侧新增“知识库配置”，支持填写 RAGFlow 服务根地址、API Key、默认知识库名称、语言和内置解析器。
- 保存前验证 RAGFlow 凭据；按名称创建知识库，同名知识库存在时幂等复用，并保存远端 Dataset ID。
- API Key 仅提交到后端，加密持久化；GET 只返回掩码和是否已配置，不返回明文。
- 为文档、上传、模板、Run、Task、解析产物和配置响应增加统一 `storage_locations` 标记，并在文档列表、运行页和配置页展示。
- 当前未同步到 RAGFlow 的历史文档继续标记为 DataWeave 本地文件，不提前伪装为远端数据。
### 验收标准
- [ ] 配置页可读取、修改并保存 RAGFlow 配置，首次保存必须提供 Key，后续留空可保留原 Key。
- [ ] 保存成功后通过真实 RAGFlow HTTP API 创建填写名称的知识库，重复保存不创建同名副本；响应明确区分本次创建或复用。
- [ ] 数据库、API、日志和前端响应中不存在 API Key 明文；本地加密 Key 文件权限为 `0600`。
- [ ] 核心 API 返回存储位置，前端能区分 DataWeave 本地数据与 RAGFlow 数据。
- [ ] Provider Mock、加密持久化、Dataset 创建/复用和存储标记有后端测试；前端生产构建通过。
### 非目标
- 本 Issue 不迁移或上传已有文章到 RAGFlow；文档同步由 DW-052/DW-053 完成。
<!-- /issue-body -->

# Known Bugs · 已知缺陷

## [DW-046] 修复领域上下文预览任务与后端运行进度不一致
<!-- issue: number=46; state=open; labels=bug,priority:P1,area:frontend,domain-context,progress; assignees= -->
<!-- issue-body -->
### 问题
- 前端注入 Context 节点，顶部进度来自后端，统计口径不一致。
### 验收标准
- [ ] 预览节点不计入后端百分比；正式接入后统一 DAG；SSE 不倒退。
### 关联
- DW-016、DW-017。
<!-- /issue-body -->

---

## [DW-047] 修复模板配置仅保存在浏览器导致跨设备丢失
<!-- issue: number=47; state=open; labels=bug,priority:P1,area:fullstack,templates,persistence; assignees= -->
<!-- issue-body -->
### 问题
- localStorage 配置无法跨设备同步，也不能可靠复现历史运行。
### 验收标准
- [ ] 后端持久化不可变模板版本，Run 引用版本，旧配置有迁移策略。
<!-- /issue-body -->

---

## [DW-048] 修复领域上下文审核刷新后状态丢失
<!-- issue: number=48; state=open; labels=bug,priority:P1,area:fullstack,domain-context,review; assignees= -->
<!-- issue-body -->
### 问题
- 接受/排除只更新组件本地状态，刷新后丢失。
### 验收标准
- [ ] 审核写入后端，刷新一致，失败时 UI 回滚并提示；依赖 DW-025、DW-026。
<!-- /issue-body -->

---

## [DW-049] 修复知识产物卡片将任务完成误认为正式产物可用
<!-- issue: number=49; state=open; labels=bug,priority:P2,area:frontend,artifacts,status; assignees= -->
<!-- issue-body -->
### 问题
- 卡片按 Task 推导可用性，可能将模拟任务显示为真实产物。
### 验收标准
- [ ] 以 Manifest 区分未构建、构建中、Draft、失败、发布、失效。
<!-- /issue-body -->

---

## [DW-050] 修复已发布状态缺少 Artifact Release 一致性校验
<!-- issue: number=50; state=open; labels=bug,priority:P2,area:backend,artifacts,release; assignees= -->
<!-- issue-body -->
### 问题
- Publish 仅切换 Run 状态，未校验产物、输入版本和 Context Release。
### 验收标准
- [ ] 发布前完整校验，失败不切换指针，记录可回溯 Manifest/Release。
<!-- /issue-body -->
