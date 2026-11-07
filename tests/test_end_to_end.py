"""Offline mode tests: not a claim that the live OpenAI agent was tested."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

HEADERS = {"X-Approval-Token": "tests-only-token"}

def create(client, ref="INV-X-100"):
    return client.post("/agent/chat", json={"message": f"Prepare invoice for Acme Corp, $2,500, description: Consulting services, reference {ref}."})


def test_backend_ui_and_summary():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert "finpilot" in client.get("/").text
        assert client.get("/app.css").status_code == 200
        assert client.get("/app.js").status_code == 200
        assert client.get("/overview").json()["customer_count"] == 4
        assert client.get("/policy").json()["maximum_invoice_cents"] == 5000000
        assert client.get("/health").json()["agent_mode"] == "offline_demo"


def test_demo_read_tools():
    with TestClient(app) as client:
        names=client.post("/agent/chat",json={"message":"Show customers"}).json()
        assert "Acme Corp" in names["answer"]
        assert names["trace"][0]["tool"] == "list_customers"
        assert client.post("/agent/chat",json={"message":"What is the approval policy?"}).json()["trace"][0]["tool"]=="retrieve_policy"
        assert client.post("/agent/chat",json={"message":"List recent invoices"}).json()["trace"][0]["tool"]=="search_invoices"


def test_agent_proposal_approval_and_no_unauthorized_write():
    with TestClient(app) as client:
        resp=create(client)
        assert resp.status_code==200,resp.text
        run=resp.json()
        assert run["status"]=="pending_approval",run
        assert [i["tool"] for i in run["trace"]]==["lookup_customer","retrieve_policy","check_duplicate","prepare_invoice_draft"]
        assert client.get("/invoices").json()==[]
        assert client.get("/agent/threads/"+run["thread_id"]).json()["request_id"]==run["request_id"]
        url="/agent/threads/"+run["thread_id"]+"/decision"
        assert client.post(url,json={"decision":"approve"}).status_code==403
        assert client.get("/invoices").json()==[]
        result=client.post(url,json={"decision":"approve"},headers=HEADERS)
        assert result.status_code==200,result.text
        assert result.json()["status"]=="approved"
        assert client.post(url,json={"decision":"approve"},headers=HEADERS).status_code==200
        assert len(client.get("/invoices").json())==1
        assert client.get("/overview").json()["draft_total_cents"]==250000
        assert [a["action"] for a in client.get("/audit").json()]==["proposal_approved","proposal_created"]
        assert client.post(url,json={"decision":"reject"},headers=HEADERS).status_code==409


def test_rejection_is_final():
    with TestClient(app) as client:
        run=create(client,"INV-REJ-001").json()
        url="/agent/threads/"+run["thread_id"]+"/decision"
        assert client.post(url,json={"decision":"reject"},headers=HEADERS).json()["status"]=="rejected"
        assert client.get("/invoices").json()==[]
        assert client.post(url,json={"decision":"approve"},headers=HEADERS).status_code==409


def test_duplicate_oversized_and_missing_fields():
    with TestClient(app) as client:
        assert create(client,"INV-DUP-001").json()["status"]=="pending_approval"
        duplicate=create(client,"INV-DUP-001").json()
        assert duplicate["status"]=="blocked",duplicate
        assert len(client.get("/requests").json())==1
        large=client.post("/agent/chat",json={"message":"Prepare invoice for Acme Corp, $50001, description: Consulting services, reference INV-HIGH-001."}).json()
        assert large["status"]=="blocked",large
        missing=client.post("/agent/chat",json={"message":"Prepare invoice for Acme Corp, $100"}).json()
        assert missing["status"]=="needs_details",missing
        assert client.get("/invoices").json()==[]


@pytest.mark.parametrize("fault",range(40))
def test_40_reliability_fault_scenarios(fault):
    """40 isolated request replay, approval replay, bad-token and rejection scenarios."""
    with TestClient(app) as client:
        ref=f"INJ-{fault:03d}"
        run=create(client,ref).json()
        rid=run["request_id"]
        url="/agent/threads/"+run["thread_id"]+"/decision"
        if fault%4==0:
            # Network/client retries should never create a second proposal.
            assert create(client,ref).json()["status"]=="blocked"
            assert client.post(url,json={"decision":"approve"},headers=HEADERS).status_code==200
            assert len(client.get("/invoices").json())==1
        elif fault%4==1:
            # Approval retry: same draft id.
            first=client.post(url,json={"decision":"approve"},headers=HEADERS).json()
            second=client.post(url,json={"decision":"approve"},headers=HEADERS).json()
            assert first["request_id"]==second["request_id"]
            assert len(client.get("/invoices").json())==1
        elif fault%4==2:
            # Unauthorized review cannot create drafts.
            assert client.post(url,json={"decision":"approve"},headers={"X-Approval-Token":"bad"}).status_code==403
            assert client.get("/invoices").json()==[]
            assert client.get("/requests/"+str(rid)).json()["status"]=="pending"
        else:
            # Rejection replay cannot become approval.
            assert client.post(url,json={"decision":"reject"},headers=HEADERS).status_code==200
            assert client.post(url,json={"decision":"approve"},headers=HEADERS).status_code==409
            assert client.get("/invoices").json()==[]


def test_case_insensitive_duplicate_and_invalid_decimal_precision():
    with TestClient(app) as client:
        assert create(client,"INV-CASE-01").json()["status"]=="pending_approval"
        assert create(client,"inv-case-01").json()["status"]=="blocked"
        invalid=client.post('/agent/chat',json={'message':'Prepare invoice for Acme Corp, $250.123, description: Consulting services, reference INV-DECIMAL-01.'}).json()
        assert invalid['status']=='needs_details'
        assert len(client.get('/requests').json())==1


def test_concurrent_duplicate_reservations_create_at_most_one():
    from concurrent.futures import ThreadPoolExecutor
    with TestClient(app) as client:
        def submit(i):
            return client.post('/requests',json={'customer_id':1,'external_reference':'CONCURRENT-001',
                'amount_cents':12000,'description':'Parallel test',
                'idempotency_key':f'parallel-request-key-{i}'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(submit,range(2)))
        assert sorted(r.status_code for r in outcomes)==[201,409]
        assert len(client.get('/requests').json())==1


def test_concurrent_approval_creates_at_most_one_draft():
    from concurrent.futures import ThreadPoolExecutor
    with TestClient(app) as client:
        rid=client.post('/requests',json={'customer_id':1,'external_reference':'CONCURRENT-APPROVE-01',
            'amount_cents':12000,'description':'Parallel approval test','idempotency_key':'concurrent-approve-key'}).json()['id']
        def decide(_):
            return client.post(f'/requests/{rid}/decision',json={'decision':'approve'},headers=HEADERS)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(decide,range(2)))
        assert all(r.status_code in (200,409) for r in outcomes)
        assert len(client.get('/invoices').json())==1
        assert client.post(f'/requests/{rid}/decision',json={'decision':'approve'},headers=HEADERS).status_code==200
