"""Run frozen cases through localhost with two workers; no application changes."""
import concurrent.futures
import hashlib
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

HERE=Path(__file__).resolve().parent
plan_path=HERE/'cases.json'
plan=json.loads(plan_path.read_text(encoding='utf-8'))
output=HERE/'raw-results.json'
if output.exists(): raise SystemExit('Refusing to overwrite results')
jobs=[(case,1) for case in plan['cases']]
jobs += [(case,iteration) for iteration in range(2,6) for case in plan['cases'] if case['repeat']]
report={'started_at':datetime.now(timezone.utc).isoformat(),'case_sha256':hashlib.sha256(plan_path.read_bytes()).hexdigest(),'results':[]}
def run(job):
    case,iteration=job
    started=time.monotonic()
    req=Request(f"http://127.0.0.1:8000/recipes/{case['recipe_id']}/enhance",data=json.dumps({'review_text':case['review_text']}).encode(),headers={'Content-Type':'application/json'})
    row={'case_id':case['id'],'iteration':iteration,'started_at':datetime.now(timezone.utc).isoformat()}
    try:
        with urlopen(req,timeout=510) as res:
            row.update(http_status=res.status,outcome=json.load(res))
    except HTTPError as error:
        row.update(http_status=error.code,outcome=json.loads(error.read()))
    except Exception as error:
        row.update(http_status=None,error=type(error).__name__)
    row['elapsed_seconds']=round(time.monotonic()-started,2)
    return row
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for future in concurrent.futures.as_completed([pool.submit(run,job) for job in jobs]):
        row=future.result(); report['results'].append(row)
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print(len(report['results']), '/',len(jobs),row['case_id'],row['iteration'],row.get('outcome',{}).get('status',row.get('http_status')),flush=True)
report['finished_at']=datetime.now(timezone.utc).isoformat()
output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
