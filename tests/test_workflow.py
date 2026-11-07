from fastapi.testclient import TestClient  # noqa: E402
from app.main import app


def payload(key="request-00001", ref="PO-1001"):
    return {
        "customer_id": 1,
        "external_reference": ref,
        "amount_cents": 250000,
        "description": "Consulting services",
        "idempotency_key": key,
    }


def test_happy_path_and_repeated_approval():
    with TestClient(app) as client:
        result = client.post("/requests", json=payload()).json()
        assert result["status"] == "pending"
        assert client.get("/invoices").json() == []
        headers = {"X-Approval-Token": "tests-only-token"}
        first = client.post(f'/requests/{result["id"]}/decision', json={"decision": "approve"}, headers=headers)
        second = client.post(f'/requests/{result["id"]}/decision', json={"decision": "approve"}, headers=headers)
        assert first.status_code == 200
        assert first.json()["invoice_id"] == second.json()["invoice_id"]
        assert len(client.get("/invoices").json()) == 1


def test_duplicate_key_and_duplicate_reference():
    with TestClient(app) as client:
        assert client.post("/requests", json=payload("request-00002", "PO-1002")).status_code == 201
        assert client.post("/requests", json=payload("request-00002", "PO-1002")).status_code == 201
        assert client.post("/requests", json=payload("request-00003", "PO-1002")).status_code == 409


def test_incorrect_token_and_rejection():
    with TestClient(app) as client:
        rid = client.post("/requests", json=payload("request-00004", "PO-1004")).json()["id"]
        endpoint = f"/requests/{rid}/decision"
        assert client.post(endpoint, json={"decision": "approve"}, headers={"X-Approval-Token": "wrong"}).status_code == 403
        assert client.post(endpoint, json={"decision": "reject"}, headers={"X-Approval-Token": "tests-only-token"}).json()["status"] == "rejected"
        assert client.post(endpoint, json={"decision": "approve"}, headers={"X-Approval-Token": "tests-only-token"}).status_code == 409


def test_invalid_amount_and_missing_customer():
    with TestClient(app) as client:
        invalid = payload("request-00005", "PO-1005")
        invalid["amount_cents"] = -1
        assert client.post("/requests", json=invalid).status_code == 422
        invalid["amount_cents"] = 5_000_001
        assert client.post("/requests", json=invalid).status_code == 422
        invalid["amount_cents"] = 25_000
        invalid["customer_id"] = 9999
        assert client.post("/requests", json=invalid).status_code == 404
