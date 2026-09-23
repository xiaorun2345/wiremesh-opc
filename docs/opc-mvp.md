# 丝网 OPC MVP

## 运行模式

- `cd frontend && npm run dev:mock`：无需后端，使用前端模拟数据。
- `cd frontend && npm run dev`：连接 `/api/v2` 真实后端。
- `python main.py`：启动 FastAPI，默认监听 `8000`。

生产环境使用 Alembic 执行数据库迁移：

```bash
alembic upgrade head
```

## 核心业务闭环

```text
询盘 → 图纸解析 → 规格确认 → 确定性报价 → 人工审批
     → 工厂匹配 → 订单排产 → 质检 → 物流 → 售后
```

大模型负责理解询盘、提取规格和生成说明；金额由
`app/core/skill/wire_mesh_pricing.py` 中的确定性规则计算。

## 主要接口

### 报价和审批

- `POST /api/v2/quotes/preview`
- `GET /api/v2/quotes`
- `GET /api/v2/quotes/{quote_id}`
- `POST /api/v2/quotes/{quote_id}/submit`
- `POST /api/v2/quotes/{quote_id}/decision`

### 业务资料

- `/api/v2/opc/inquiries`
- `/api/v2/opc/customers`
- `/api/v2/opc/factories`
- `/api/v2/opc/orders`
- `/api/v2/opc/knowledge`
- `GET /api/v2/opc/analytics`

上述资源接口均要求登录，并按当前用户隔离数据。客户、工厂、询盘、
订单和知识库支持列表、新建、修改和删除。

## 企业微信

在 `.env` 中配置：

```text
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...
PUBLIC_BASE_URL=https://your-opc.example.com
```

未配置 Webhook 时，提交审批仍会成功并持久化为 `PENDING_APPROVAL`，
但不会向外发送消息。企业微信仅作为通知入口，最终审批在登录后的平台内完成。

## 数据与安全

- `.env`、虚拟环境、上传文件和本地数据库已加入 `.gitignore`。
- 仓库中不应保存真实 API Key、Webhook、数据库密码或客户资料。
- 生产环境必须更换 `SECRET_KEY`，启用 HTTPS，并限制 CORS 来源。
- 价格目录、材料单价、加工费和利润控制线应由管理员维护并保留版本。
