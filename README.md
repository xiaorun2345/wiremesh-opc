# WireMesh OPC

面向丝网行业一人公司的开源 AI 工作台。系统把询盘整理、图纸识别、规格结构化、确定性报价、工厂匹配、报价审批、订单交付和知识沉淀连接成一条可审核的业务流程。

> AI 负责提取、整理和建议；价格由规则引擎计算；人负责客户、技术、利润和品控；合作工厂负责生产交付。

## 功能

- 多渠道询盘接收与状态管理
- PDF、DWG、DXF、JPG、PNG 文件处理
- 丝网专用多模态图纸识别
- 丝径、网孔、材质、尺寸、数量和表面处理提取
- 低置信度字段人工确认与断点续跑
- 材料、加工、表面处理和包装价格版本管理
- 理论重量、成本、毛利和报价确定性计算
- 基于真实工厂档案的能力、质量、交期匹配
- 中英文风格报价 PDF 与 Excel 输出
- 企业微信待审批通知
- 报价批准、退回和一键转订单
- 客户、跟进、工厂、订单、质检、物流与异常管理
- 知识资料切片、ChromaDB 索引与检索
- 操作审计、运营指标与 CSV 月报
- Celery + Redis 持久化后台任务

## 工作流

```text
渠道询盘 / 图纸上传
          ↓
文件分类与解析策略决策
          ↓
Text / CAD / Vision Agent
          ↓
WireMeshSpecAgent
          ↓
低置信度？ ── 是 → 人工确认 → 断点续跑
          │
          否
          ↓
确定性报价引擎
          ↓
真实工厂数据库匹配
          ↓
PDF / Excel 报价
          ↓
企业微信人工审批
          ↓
订单 → 排产 → 质检 → 装柜 → 运输 → 交付
```

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Element Plus、Pinia
- API：FastAPI、Pydantic、SQLAlchemy、Alembic
- 工作流：自研 Orchestrator、LangGraph DecisionAgent
- 后台任务：Celery、Redis
- 文件：MinIO
- 知识库：ChromaDB
- 数据库：MySQL 8，开发模式可使用 SQLite
- 报告：ReportLab、OpenPyXL

## 快速体验

只运行带模拟数据的前端：

```bash
cd frontend
npm install
npm run dev:mock
```

访问 `http://localhost:5173`，任意非空用户名和密码均可进入 mock 演示。

## Docker 部署

```bash
cp .env.example .env
# 修改数据库密码、SECRET_KEY、模型和 Webhook 配置
docker compose -f docker/docker-compose.yml up -d --build
```

容器启动时会自动执行 Alembic 数据库迁移。

访问：

- Web：`http://localhost`
- API 文档：`http://localhost/docs`
- MinIO：`http://localhost:9001`

## 本地开发

后端要求 Python 3.11+：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python main.py
```

真实后端前端：

```bash
cd frontend
npm install
npm run dev
```

## 核心 API

- `/api/v2/tasks`：图纸任务、人工续跑
- `/api/v2/quotes`：报价计算、审批、文件和转订单
- `/api/v2/opc/inquiries`：询盘
- `/api/v2/opc/customers`：客户
- `/api/v2/opc/factories`：合作工厂
- `/api/v2/opc/orders`：订单
- `/api/v2/opc/knowledge`：知识资料
- `/api/v2/automation/prices`：价格版本
- `/api/v2/automation/followups`：客户跟进
- `/api/v2/automation/orders/{id}/events`：订单事件
- `/api/v2/automation/channels/inbound`：渠道 Webhook
- `/api/v2/automation/audit`：审计日志

## 报价安全原则

大模型不能填写价格。模型只返回结构化规格，所有金额由 [`wire_mesh_pricing.py`](app/core/skill/wire_mesh_pricing.py) 读取生效价格版本并确定性计算。成本和毛利仅用于内部审批，不写入客户报价单。

## 安全

- 不要提交 `.env`、客户资料、报价数据和 API Key。
- 生产环境必须更换 `SECRET_KEY`、数据库密码和 Webhook Token。
- 如果历史提交曾包含真实密钥，请立即在服务商后台轮换；仅从当前文件删除并不能使旧密钥失效。
- 企业微信仅用于官方 Webhook/自建应用，不使用个人微信非官方协议。

## 测试

```bash
pytest
cd frontend && npm run build
```

详细部署和业务说明见 [`docs/opc-mvp.md`](docs/opc-mvp.md)。

## License

MIT
