"""Executable 150-case OFFLINE SANITY harness. Explicitly not a live-LLM eval."""
import argparse
import json
import os
import tempfile
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def evaluate(cases_file: Path, output: Path, limit: int | None = None):
    # Set these before importing the backend, ensuring no real local/demo database is touched.
    with tempfile.TemporaryDirectory(prefix='finpilot-eval-') as temp_dir:
        os.environ['APP_DATABASE_URL']='sqlite:///'+str(Path(temp_dir)/'eval.sqlite')
        os.environ['APP_APPROVAL_TOKEN']='evaluation-only-token'
        os.environ.pop('OPENAI_API_KEY',None)  # offline run, no model costs
        from fastapi.testclient import TestClient
        from app.main import app
        cases=[json.loads(line) for line in cases_file.read_text().splitlines() if line.strip()]
        if limit is not None:cases=cases[:limit]
        results=[]
        with TestClient(app) as client:
            for case in cases:
                if case.get('seed_ref'):
                    init=client.post('/requests',json={'customer_id':1,'external_reference':case['seed_ref'],
                        'amount_cents':25000,'description':'Existing proposal',
                        'idempotency_key':'eval-seed-'+case['id']})
                    assert init.status_code==201,init.text
                t=time.perf_counter()
                response=client.post('/agent/chat',json={'message':case['message']})
                elapsed_ms=round((time.perf_counter()-t)*1000,2)
                data=response.json()
                actual_tools=[x['tool'] for x in data.get('trace',[])]
                invoices=client.get('/invoices').json()
                status_ok=response.status_code==200 and data.get('status')==case['status']
                tools_ok=actual_tools==case['expected_tools']
                safety_ok=not invoices # no approvals in these benchmark tasks
                results.append({'id':case['id'],'category':case['category'],'passed':status_ok and tools_ok and safety_ok,
                                'status_ok':status_ok,'tools_ok':tools_ok,'safety_ok':safety_ok,
                                'actual_status':data.get('status'),'actual_tools':actual_tools,
                                'expected_status':case['status'],'expected_tools':case['expected_tools'],
                                'duration_ms':elapsed_ms})
        total=len(results);success=sum(row['passed'] for row in results)
        stats={cat:{'passed':sum(row['passed'] for row in results if row['category']==cat),
                    'total':sum(row['category']==cat for row in results)} for cat in sorted({r['category'] for r in results})}
        report={'kind':'deterministic_offline_sanity_check','disclaimer':'No live OpenAI calls; this cannot estimate model task-completion or tool-selection accuracy.',
                'timestamp_utc':datetime.now(timezone.utc).isoformat(),'cases':total,'passed':success,
                'expected_tools_matched':sum(r['tools_ok'] for r in results),'no_unauthorized_invoice_writes':all(r['safety_ok'] for r in results),
                'by_category':stats,'details':results}
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,indent=2))
        print(f'Offline sanity checks: {success}/{total} passed. Report: {output}')
        for k,v in stats.items():print(f'  {k}: {v["passed"]}/{v["total"]}')
        return success==total

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases',type=Path,default=ROOT/'data/evaluation_cases.jsonl')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/offline_evaluation.json')
    parser.add_argument('--limit',type=int,default=None)
    args=parser.parse_args()
    raise SystemExit(0 if evaluate(args.cases,args.output,args.limit) else 1)
