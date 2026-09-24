"""Deterministic provider failure injection through FastAPI, without paid calls."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'src'))
from api import create_app,get_extractor
from llm_pipeline.grounded import GroundedPlanner

class Client:
    def __init__(self,mode):
        self.mode=mode; self.calls=0
        self.chat=SimpleNamespace(completions=self)
    def with_options(self,**kwargs): return self
    def create(self,**kwargs):
        self.calls+=1
        prompt=kwargs['messages'][0]['content']
        stage='interpret' if prompt.startswith('Identify ALL') else 'fidelity' if prompt.startswith('Check source') else 'consistency' if prompt.startswith('Check ONLY') else 'edits'
        if self.mode==stage+'_timeout': raise TimeoutError('Injected timeout')
        if self.mode==stage+'_bad_json': content='not valid JSON'
        elif stage=='interpret':
            content=json.dumps({'changes':[{'id':'1','source_quote':'I used half a cup of white sugar.','action':'quantity','timing':'performed','target':'white sugar','amount_mode':'absolute','amount':'1/2','unit':'cup','description':'Use half cup'}],'unresolved':[]})
        elif stage=='edits': content='{"edits":[]}'
        elif stage=='fidelity': content='{"status":"faithful","issues":[]}'
        else: content='{"status":"consistent","issues":[]}'
        return SimpleNamespace(usage=None,choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=content))])

rows=[]
for mode in ['interpret_timeout','interpret_bad_json','fidelity_timeout','consistency_timeout','consistency_bad_json']:
    app=create_app(); provider=Client(mode)
    extractor=SimpleNamespace(client=provider)
    extractor.plan_review=GroundedPlanner(extractor).plan
    app.dependency_overrides[get_extractor]=lambda:extractor
    with TestClient(app) as client:
        original=client.get('/recipes/10813').json()['recipe']
        res=client.post('/recipes/10813/enhance',json={'review_text':'I used half a cup of white sugar.'})
        body=res.json()
        if mode.startswith('consistency'):
            passed=res.status_code==200 and body['status']=='failed' and body['result']['recipe']==original and body['enhanced_recipe'] is None and body['result']['changes']==[]
        else:
            passed=res.status_code==502 and body.get('detail',{}).get('code')=='planning_failed' and 'enhanced_recipe' not in body
        rows.append({'case':mode,'http_status':res.status_code,'passed':passed,'mock_calls':provider.calls,'response':body})
out=HERE/'fault-results.json'
if out.exists(): raise SystemExit('Refusing overwrite')
out.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
print([(r['case'],r['passed']) for r in rows])
assert all(r['passed'] for r in rows)
