"""Enterprise WeChat notification adapter.

This adapter uses an official group-bot webhook when configured. Approval is
still completed in the authenticated OPC platform; the WeCom message links the
reviewer back to the quote page.
"""
import httpx

from config.settings import settings


async def notify_quote_review(quote_id: str, quote: dict) -> bool:
    if not settings.WECOM_WEBHOOK_URL:
        return False

    review_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/quotes/{quote_id}"
    content = (
        f"### 丝网报价待人工确认\n"
        f">报价编号：`{quote_id}`\n"
        f">产品：{quote['spec']['product_type']}\n"
        f">面积：{quote['area_m2']} m²\n"
        f">报价：{quote['currency']} {quote['quote_total']}\n"
        f">毛利率：{quote['margin_rate']:.1%}\n"
        f">[打开平台审核]({review_url})"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            settings.WECOM_WEBHOOK_URL,
            json={"msgtype": "markdown", "markdown": {"content": content}},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("errcode") == 0
