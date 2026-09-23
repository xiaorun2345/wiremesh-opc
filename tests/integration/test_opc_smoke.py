import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_opc_end_to_end_smoke():
    username = f"opc-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        auth = client.post("/api/v2/auth/register", json={"username": username, "password": "test-password-123"})
        assert auth.status_code == 200, auth.text
        headers = {"Authorization": f"Bearer {auth.json()['access_token']}"}

        customer = client.post("/api/v2/opc/customers", headers=headers, json={"name":"测试采购商","region":"中国"})
        assert customer.status_code == 201, customer.text
        customer_id = customer.json()["id"]

        factory = client.post("/api/v2/opc/factories", headers=headers, json={
            "name":"测试丝网厂","products":["welded_mesh"],
            "surfaces":["hot_dip_galvanized"],"certifications":["ISO 9001"],
            "lead_days":12,"on_time_rate":0.96,"quality_score":93,
        })
        assert factory.status_code == 201, factory.text
        factory_id = factory.json()["id"]

        price = client.post("/api/v2/automation/prices", headers=headers, json={
            "category":"material","item_key":"low_carbon_steel","unit":"kg","unit_price":4.8,
        })
        assert price.status_code == 201, price.text

        quote = client.post("/api/v2/quotes/preview", headers=headers, json={
            "product_type":"welded_mesh","material":"low_carbon_steel",
            "wire_diameter_mm":3.5,"mesh_size_mm":50,"width_m":2,"length_m":3,"quantity":100,
            "surface_treatment":"hot_dip_galvanized","packaging":"export",
            "margin_rate":0.15,"freight":800,"currency":"CNY",
        })
        assert quote.status_code == 200, quote.text
        payload = quote.json()
        assert payload["factory_matches"][0]["id"] == factory_id
        quote_id = payload["quote_id"]

        assert client.post(f"/api/v2/quotes/{quote_id}/submit", headers=headers).status_code == 200
        assert client.post(f"/api/v2/quotes/{quote_id}/decision", headers=headers, json={"decision":"approve","note":"规格和利润已确认"}).status_code == 200

        pdf = client.get(f"/api/v2/quotes/{quote_id}/download?format=pdf", headers=headers)
        assert pdf.status_code == 200
        assert pdf.content.startswith(b"%PDF")

        order = client.post(f"/api/v2/quotes/{quote_id}/convert-order", headers=headers, json={"customer_id":customer_id,"factory_id":factory_id})
        assert order.status_code == 201, order.text
        order_id = order.json()["id"]

        event = client.post(f"/api/v2/automation/orders/{order_id}/events", headers=headers, json={"event_type":"status_changed","to_status":"生产中","data":{"operator":"test"}})
        assert event.status_code == 201, event.text
        assert event.json()["status"] == "生产中"

        analytics = client.get("/api/v2/opc/analytics", headers=headers)
        assert analytics.status_code == 200
        assert analytics.json()["customers"] >= 1
        assert analytics.json()["orders"] >= 1
