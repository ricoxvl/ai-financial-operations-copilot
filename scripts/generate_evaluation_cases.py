"""Generate frozen, synthetic offline sanity-check cases; this is NOT an LLM benchmark."""
import json
from pathlib import Path

cases=[]
for i in range(20):
    cases.append(dict(id=f"customer-{i:03d}", category="customer_lookup", message="Show customers", status="completed", expected_tools=["list_customers"]))
for i in range(30):
    cases.append(dict(id=f"search-{i:03d}", category="invoice_search", message="List recent invoices", status="completed", expected_tools=["search_invoices"]))
for i in range(30):
    company=["Acme Corp","Northstar Labs","Summit Retail","BluePeak Analytics"][i%4]
    cases.append(dict(id=f"draft-{i:03d}",category="draft_proposal",message=f"Prepare invoice for {company}, ${100+i*37}, description: Process design project, reference EVAL-DRAFT-{i:03d}.", status="pending_approval", expected_tools=["lookup_customer","retrieve_policy","check_duplicate","prepare_invoice_draft"]))
for i in range(25):
    cases.append(dict(id=f"duplicate-{i:03d}",category="duplicate_detection",message=f"Prepare invoice for Acme Corp, $250, description: Consulting services, reference EVAL-DUP-{i:03d}.", status="blocked", expected_tools=["lookup_customer","retrieve_policy","check_duplicate"], seed_ref=f"EVAL-DUP-{i:03d}"))
for i in range(20):
    cases.append(dict(id=f"policy-{i:03d}",category="policy",message="What is the approval policy?",status="completed",expected_tools=["retrieve_policy"]))
for i in range(15):
    cases.append(dict(id=f"ambiguous-{i:03d}",category="ambiguous_input",message="Prepare invoice for Acme Corp, $250",status="needs_details",expected_tools=[]))
for i in range(10):
    cases.append(dict(id=f"failure-{i:03d}",category="policy_error",message=f"Prepare invoice for Acme Corp, $50001, description: Consulting services, reference EVAL-HIGH-{i:03d}.", status="blocked", expected_tools=["lookup_customer","retrieve_policy","check_duplicate","prepare_invoice_draft"]))
assert len(cases)==150
out=Path(__file__).resolve().parent.parent/'data/evaluation_cases.jsonl'
out.write_text(''.join(json.dumps(c,sort_keys=True)+'\n' for c in cases))
print('Generated',len(cases),'synthetic cases:',out)
