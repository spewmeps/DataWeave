# DataWeave Development

当前 `src` 提供第一个可运行的纵向切片：论文上传、模板配置、异步解析运行和任务详情。

## One-command Start

在项目根目录执行：

```bash
./start-dataweave.sh
```

脚本默认执行重启：如果 DataWeave 已运行，会先安全停止前后端，再启动全部服务并检查健康状态。SQLite、上传文件、解析产物和历史日志均保留。

```bash
./start-dataweave.sh status   # 查看状态
./start-dataweave.sh stop     # 停止全部服务
./start-dataweave.sh restart  # 显式重启，等同于不传参数
```

服务日志保存在 `src/.data/logs/services/`。

## Structure

```text
src/
├─ frontend/  Vue 3 + TypeScript + Vite 工作台
└─ backend/   FastAPI API 与阶段性 Mock Pipeline
```

Mock Pipeline 已按照最终 Run、Task、Event、Artifact 契约实现。下一阶段会把进程内任务替换为 PostgreSQL、Celery 和真实解析器，前端接口保持不变。

## Start Backend

```bash
cd src/backend
uv sync --extra dev
uv run uvicorn dataweave.main:app --reload --host 127.0.0.1 --port 8000
```

API 文档：`http://127.0.0.1:8000/docs`

## Start Frontend

```bash
cd src/frontend
npm install
npm run dev
```

浏览器打开：`http://127.0.0.1:5173`

## Verify

```bash
cd src/backend && uv run pytest -q
cd src/frontend && npm run build
```

页面内可以选择“使用示例论文”，无需准备真实 PDF 即可走通上传、模板和解析流程。

