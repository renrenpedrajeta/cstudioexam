"""Record semantic review decisions and calculate reproducible test totals."""
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
plan=json.loads((HERE/'cases.json').read_text(encoding='utf-8'))
raw=json.loads((HERE/'raw-results.json').read_text(encoding='utf-8'))
assert len(raw['results'])==56 and raw.get('finished_at')
assert hashlib.sha256((HERE/'cases.json').read_bytes()).hexdigest()==raw['case_sha256']
assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in plan['source_hashes'].items())
lookup={c['id']:c for c in plan['cases']}
notes={
 'Q01':'White sugar 3/4 cup; brown sugar preserved.', 'Q02':'Flour reduced to 2 cups.',
 'Q03':'Vanilla 4 teaspoons in ingredients and use step.', 'Q04':'Chicken broth 4 cups; simmering instructions preserved.',
 'Q05':'Cherries 1/2 cup in ingredients and blender step.', 'Q06':'Sake 1/8 cup in ingredients and simmering step.',
 'Q07':"Frosting sugar 1 1/2 cups; both batter sugars unchanged.", 'Q08':'Eggs increased to 3; other ingredients unchanged.',
 'S01':'Walnuts replaced with 1 cup pecans and mixing step updated.', 'S02':'2 cups milk chocolate chips and matching mixing step.',
 'S03':'3 cups vegetable broth and matching simmering step.', 'S04':'3/4 cup cranberries and matching blender step.',
 'S05':'1 1/2 cups pineapple juice and matching blender step.', 'S06':'1/4 cup tamari and matching simmering step.',
 'M01':'All three changes present: 3/4 cup white sugar, 3 eggs, 1 cup pecans; walnut use removed.',
 'M02':'2 1/2 cups flour, no walnuts, 1 teaspoon cinnamon with use step; dough chilled 45 minutes before spooning.',
 'M03':'1 cup mango nectar, 1/2 cup cranberries replacing cherries, refrigerated marination at least 4 hours.',
 'T03':'Finished dough chilled 20 minutes before spooning; baking preserved.', 'R01':'Garlic removed from ingredient and blender instruction.',
}
issues=[
 {'id':'H01','severity':'High','priority':1,'title':'Preparation action changes without support','cases':'A02','finding':'The review says stir parsley into soup. Published instructions use parsley as a garnish instead. Both audits approved it.','fix':'Represent and validate preparation actions and their targets, not only ingredient presence. Add a stir-versus-garnish regression.','closure':'Parsley is explicitly stirred in before serving; the wrong action is rejected in fresh and repeated cases.'},
 {'id':'H02','severity':'High','priority':2,'title':'Published description contradicts ingredient removal','cases':'M04','finding':'Three repeats publish peanut-free ingredients while the enhanced description still says topped with honey-roasted peanuts. Another run withholds this conflict.','fix':'Include affected descriptions in the edit scope or omit stale descriptions; validate the complete published recipe consistently.','closure':'No published field claims peanuts remain after removal; repeated responses agree.'},
 {'id':'H03','severity':'High','priority':3,'title':'Cooking durations misclassified as ingredient quantities','cases':'T01, T02','finding':'12-minute baking and 4-hour marination are sent to ingredient quantity matching and rejected as missing ingredients.','fix':'Separate duration and temperature intents from ingredient amounts before quantity arithmetic.','closure':'Both duration requests apply without ingredient changes; new duration phrasings pass.'},
 {'id':'H04','severity':'High','priority':4,'title':'Complex plans remain incomplete or misordered','cases':'M02','finding':'Only 2 of 5 runs complete. Two runs chill before the dough is fully mixed. Another omits cinnamon from ingredients. Safeguards withhold these outputs.','fix':'Require each addition in both ingredients and preparation, and model chilling after mixing as well as before shaping.','closure':'All required changes and ordering pass repeated runs; invalid candidates remain unpublished.'},
 {'id':'H05','severity':'High','priority':5,'title':'Quantity text lock rejects equivalent grammar','cases':'M03','finding':"Two runs are rejected when repair changes '1 cups mango nectar' to '1 cup mango nectar'. The numerical quantity is unchanged.",'fix':'Generate grammatical unit text and compare structured quantity, unit and ingredient identity when protecting calculated edits.','closure':'Equivalent singular/plural formatting is accepted without allowing quantity overrides.'},
 {'id':'H06','severity':'High','priority':6,'title':'Ingredient preparation words cause false rejection','cases':'A01','finding':"The checker requires 'finely grated orange zest' verbatim in instructions and rejects the valid short name 'orange zest'.",'fix':'Normalize ingredient identity separately from preparation descriptors while retaining ambiguity checks.','closure':'Orange-zest addition passes with the short use name; genuinely missing uses still fail.'},
 {'id':'O01','severity':'Medium','priority':7,'title':'Provider failures interrupt repeated requests','cases':'M03 run 5, M04 run 5, T03 runs 4-5','finding':'Three HTTP 502 responses name RateLimitError. One further run returns failed because consistency validation could not complete. No enhanced recipe is returned.','fix':'Identify provider rate-limit versus quota failures, expose actionable errors, and add bounded backoff only for retryable failures.','closure':'Recoverable failures are bounded and explained; no partial publication. Retest affected cases after provider capacity is confirmed.'},
]
rows=[]; changes=[]
for row in sorted(raw['results'],key=lambda r:(list(lookup).index(r['case_id']),r['iteration'])):
    case=lookup[row['case_id']]; o=row.get('outcome',{}); p=o.get('planning',{}); result=o.get('result',{})
    status=o.get('status','HTTP '+str(row['http_status']))
    messages=p.get('issues',[])+(o.get('consistency_check') or {}).get('issues',[])+o.get('detail',{}).get('issues',[])
    category='Correct'; severity='None'; issue=''; observed=notes.get(case['id'],'Original preserved; requested abstention was correct.')
    if status=='applied' and case['id']=='A02':
        category='Incorrect publication'; severity='High'; issue='H01'
        observed='Parsley is added as a garnish, although the source review explicitly says it was stirred into the soup.'
        assert 'garnish with' in ' '.join(result['recipe']['instructions'])
    elif status=='applied' and case['id']=='M04':
        category='Incorrect publication'; severity='High'; issue='H02'
        observed='Ingredients and instructions omit peanuts, but the published description still claims the soup is topped with honey-roasted peanuts.'
        assert 'topped with honey-roasted peanuts' in o['enhanced_recipe']['description']
    elif row['http_status']!=200 or status=='failed':
        category='Technical failure'; severity='Medium'; issue='O01'; observed='No enhanced recipe returned. '+' '.join(messages)
    elif status != case['expected_status']:
        severity='High'
        mapping={'M02':('Incomplete plan','H04'),'M03':('False rejection','H05'),'M04':('Incomplete plan','H02'),
                 'T01':('False rejection','H03'),'T02':('False rejection','H03'),'A01':('False rejection','H06')}
        category,issue=mapping[case['id']]
        observed={'M02':'Valid request not completed: chilling occurs before mixing is finished, or cinnamon is missing from ingredients.',
                  'M03':"Valid request withheld after grammar-only change from '1 cups' to '1 cup' violates the exact calculated-text lock.",
                  'M04':'Valid request withheld because the description still mentions the removed peanut garnish.',
                  'T01':'Baking time classified as an ingredient quantity; no ingredient named baking time.',
                  'T02':'Marination time classified as an ingredient quantity; no ingredient named marinate time.',
                  'A01':'Valid orange-zest use rejected because the short ingredient name omits finely grated.'}[case['id']]
    if status!='applied' and result:
        assert result['recipe']==o['original'] and result['changes']==[] and o['enhanced_recipe'] is None
    if status=='applied':
        assert o['enhanced_recipe']['ingredients']==result['recipe']['ingredients']
        assert o['enhanced_recipe']['instructions']==result['recipe']['instructions']
        for c in result.get('changes',[]):
            changes.append([case['id'],row['iteration'],c['type'],c['operation'],c['from_text'],c['to_text']])
        if case['id']=='M04': changes.append([case['id'],row['iteration'],'description','retained',o['original']['description'],o['enhanced_recipe']['description']])
    calls=p.get('calls',[])
    tokens=sum(c.get('usage',{}).get('total_tokens',0) for c in calls)
    rows.append({**case,'iteration':row['iteration'],'actual_status':status,'http_status':row['http_status'],
        'grade':category,'severity':severity,'issue_id':issue,'observed':observed,'validation_messages':' '.join(messages),
        'seconds':row['elapsed_seconds'],'recorded_calls':len(calls),'recorded_tokens':tokens,
        'usage_available':bool(calls),'repaired':any(c.get('stage')=='repair' for c in calls),
        'endpoint':f"http://127.0.0.1:8000/recipes/{case['recipe_id']}/enhance"})
first=[r for r in rows if r['iteration']==1]
summary={'unique_cases':len(first),'live_requests':len(rows),'first_correct':sum(r['grade']=='Correct' for r in first),
         'first_supported':sum(r['expected_status']=='applied' for r in first),
         'first_supported_correct':sum(r['grade']=='Correct' and r['expected_status']=='applied' for r in first),
         'grades':dict(Counter(r['grade'] for r in rows)), 'recorded_planning_calls':sum(r['recorded_calls'] for r in rows),
         'recorded_planning_tokens':sum(r['recorded_tokens'] for r in rows),
         'usage_missing_responses':sum(not r['usage_available'] for r in rows),
         'regression_tests':56,'fault_tests':5,'source_unchanged':True,
         'started_at':raw['started_at'],'finished_at':raw['finished_at']}
payload={'summary':summary,'rows':rows,'issues':issues,'changes':changes,'plan_hash':raw['case_sha256']}
(HERE/'reviewed-results.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2))
