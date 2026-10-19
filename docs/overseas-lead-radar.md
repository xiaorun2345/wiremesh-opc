# 海外商机雷达

WireMesh OPC 只采集官方 API、公开 RSS 或明确授权的数据源，不自动登录、绕过验证码或抓取限制访问的 B2B 平台页面。

## 支持的数据源

| Provider | 配置 | 备注 |
|---|---|---|
| `ted` | `cpv_codes`、可选 `expert_query`、`countries` | 欧盟 TED 公开采购 Search API。|
| `sam` | `api_key_env: "SAM_GOV_API_KEY"`、可选 `keyword` | 需要 SAM.gov 公共 API Key，密钥只放环境变量。|
| `contracts_finder` | `url` | 填入已获授权的英国 OCDS Search URL。|
| `rss` | `feed_url` | 只使用公开、允许订阅的 RSS/Atom Feed。|

丝网默认 TED CPV：`44313100`、`44313000`、`44313200`、`44312000`、`34928200`、`34928310`。

默认启用的数据源：

1. **TED 欧盟采购（丝网）**：使用公开 Search API，不需要 API Key。系统按 CPV `44313100`（wire-mesh fencing）、`44313000`（metal netting）、`44313200`（wire cloth）、`44312000`（fencing wire）、`34928200`（fences）、`34928310`（safety fencing）采集，同时用 `wire mesh`、`security fencing`、`mining screen` 做相关度评分。
2. **英国 Contracts Finder（丝网）**：使用公开 OCDS Search 接口 `https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search`，采集后按 `wire mesh`、`welded mesh`、`security fencing`、`metal netting`、`wire cloth` 过滤和评分。

示例 TED 配置：

```json
{
  "cpv_codes": ["44313100", "44313000", "44313200"],
  "countries": ["Malta", "Sweden", "Germany"],
  "keywords": ["gabion", "anti-climb fencing"],
  "limit": 50,
  "platform_url": "https://opc.example.com"
}
```

示例 SAM.gov 配置：

```json
{
  "api_key_env": "SAM_GOV_API_KEY",
  "keyword": "wire mesh",
  "lookback_days": 2,
  "limit": 100,
  "countries": ["US"]
}
```

示例 RSS 配置：

```json
{
  "feed_url": "https://example.gov/procurement/rss.xml",
  "keywords": ["fencing", "wire mesh"]
}
```

## 自动流程

```text
采集器 → 统一字段 → source + external_id 去重
       → 丝网规格抽取 → 相关度评分 → 海外商机池
       → ≥80 分：创建高优先级通知 → 企业微信 / 邮件（已配置时）
       → 人工确认 → 转入询盘中心 → 报价流程
```

Celery Beat 默认每 30 分钟执行一次所有启用数据源。没有配置凭据的数据源会记录失败原因，不会生成伪造商机。

## 通知配置

```text
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USERNAME=alerts@example.com
SMTP_PASSWORD=...
SMTP_FROM=alerts@example.com
NOTIFY_EMAILS=owner@example.com,sales@example.com
```

仅评分达到 80 分的商机默认即时发送；所有商机都保存在网页“海外商机”中。

不要在数据源 JSON 配置里保存 API Key、OAuth Token 或邮箱密码；配置只保存检索条件，凭据只通过环境变量或后续密钥管理服务注入。

## 合规边界

- 不采集登录后页面、需要验证码页面或禁止自动化访问的页面。
- 不将客户信息、API Key 或供应商密码写入 Git。
- 对需要密钥的来源优先通过环境变量提供，例如 `SAM_GOV_API_KEY`。
- 使用公开公告的原始链接作为来源证据，投标前仍需人工阅读原始文件并确认资格条件。
