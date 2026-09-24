import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const dir=path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1'));
const root=path.resolve(dir,'../..');
const data=JSON.parse(await fs.readFile(path.join(root,'evaluation/reliability_20260924/reviewed-results.json'),'utf8'));
const faults=JSON.parse(await fs.readFile(path.join(root,'evaluation/reliability_20260924/fault-results.json'),'utf8'));
const wb=Workbook.create();
for(const n of ['Summary','Cases','Runs','Issues','Changes','Method']) wb.worksheets.add(n);
const ink='#263244', blue='#243B53', pale='#EDF2F7';
const letters=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
function base(name,title,subtitle,widths,rows=20){
 const sh=wb.worksheets.getItem(name); sh.showGridLines=false;
 sh.getRange(`A1:${letters(widths.length-1)}${rows}`).format.font={name:'Arial',size:11,color:ink};
 sh.getRange('A1').values=[[title]];sh.getRange('A1').format.font={name:'Arial',size:17,bold:true,color:ink};
 sh.getRange('A1').format.rowHeight=28;
 sh.getRange('A2').values=[[subtitle]];sh.getRange('A2').format.font={name:'Arial',size:10,italic:true,color:'#52616F'};
 sh.getRange(`A3:${letters(widths.length-1)}3`).format.borders={bottom:{style:'thin',color:'#CBD5E1'}};
 widths.forEach((width,i)=>{sh.getRange(`${letters(i)}1:${letters(i)}${rows}`).format.columnWidth=width;});
 return sh;
}
function table(name,title,subtitle,headers,values,widths){
 const sh=base(name,title,subtitle,widths,values.length+4);
 sh.getRange(`A4:${letters(headers.length-1)}4`).values=[headers];
 sh.getRange(`A4:${letters(headers.length-1)}4`).format={fill:blue,font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:34};
 if(values.length)sh.getRangeByIndexes(4,0,values.length,headers.length).values=values;
 const body=sh.getRange(`A5:${letters(headers.length-1)}${values.length+4}`);
 body.format.wrapText=true;body.format.verticalAlignment='top';
 values.forEach((row,i)=>{
  let lines=1;row.forEach((v,j)=>{const text=String(v??'');lines=Math.max(lines,text.split('\n').reduce((n,line)=>n+Math.max(1,Math.ceil(line.length/(widths[j]-3))),0));});
  sh.getRange(`A${i+5}:${letters(headers.length-1)}${i+5}`).format.rowHeight=Math.min(320,Math.max(32,lines*15+9));
  if(i%2===1)sh.getRange(`A${i+5}:${letters(headers.length-1)}${i+5}`).format.fill='#F5F7FA';
 });
 sh.tables.add(`A4:${letters(headers.length-1)}${values.length+4}`,true,`${name}Data`);
 sh.freezePanes.freezeRows(4);sh.freezePanes.freezeColumns(1);
 return sh;
}
const first=data.rows.filter(r=>r.iteration===1);
table('Cases','Reliability test cases','Expected outcomes were frozen before the first live request. First-run results shown.',
 ['Case','Category','Recipe ID','Review text','Expected result','Expected status','Actual status','Assessment','Issue','Observed result'],
 first.map(r=>[r.id,r.category,r.recipe_id,r.review_text,r.expected,r.expected_status,r.actual_status,r.grade,r.issue_id,r.observed]),
 [10,24,13,62,64,20,20,25,12,70]);
const runRows=data.rows.map(r=>[r.id,r.iteration,r.expected_status,r.actual_status,r.grade,r.severity,r.issue_id,r.http_status,r.seconds,r.usage_available?r.recorded_calls:null,r.usage_available?r.recorded_tokens:null,r.usage_available?(r.repaired?'Yes':'No'):'Unknown',r.observed,r.validation_messages]);
const runs=table('Runs','Individual request results','56 localhost requests. Assessments include semantic review; HTTP 200 alone is not success.',
 ['Case','Run','Expected status','Actual status','Assessment','Severity','Issue','HTTP','Seconds','Recorded planning calls','Recorded planning tokens','Repair used','Observed result','Validation message'],runRows,
 [10,9,20,20,25,12,12,10,12,19,22,15,70,105]);
runs.getRange('I5:I60').setNumberFormat('0.00');runs.getRange('J5:K60').setNumberFormat('#,##0');
const issues=table('Issues','Prioritized findings','Two publication defects take precedence over rejected requests and provider availability.',
 ['Priority','Issue','Severity','Problem','Evidence cases','Finding','Proposed fix','Closure check'],
 data.issues.map(r=>[r.priority,r.id,r.severity,r.title,r.cases,r.finding,r.fix,r.closure]),[11,10,13,45,31,73,73,69]);
table('Changes','Published recipe changes','Exact before-and-after records. M04 description rows expose the retained contradiction.',
 ['Case','Run','Field','Operation','Before','After'],data.changes,[10,9,18,16,85,85]);
const methods=[
 ['Scope','36 distinct English reviews against five existing recipes; 24 expected enhancements and 12 expected abstentions.'],
 ['Execution','Local HTTP API, two concurrent workers, no automatic test-run retries. Five predefined complex cases ran five times total each.'],
 ['Timing',`${data.summary.started_at} to ${data.summary.finished_at} (UTC). Local timezone Asia/Taipei is UTC+08:00.`],
 ['Models','Interpretation and edit generation: gpt-4o-mini. Semantic repair and fidelity: gpt-4.1. Configured consistency default: gpt-4.1.'],
 ['Expectations','Frozen before any paid call. Cases and production source hashes were verified unchanged after the run. No application fixes were made.'],
 ['Grading','Codex inspected requested changes, published change records, ingredient quantities, preparation actions and order, and relevant final descriptions. No additional LLM grader calls.'],
 ['Correct','The expected edit or abstention occurred, and no material contradiction was found in the published output. Decimal/fraction equivalents and harmless grammar differences are accepted.'],
 ['Incorrect publication','Status applied with a source-fidelity error or a contradictory published recipe field. A02 changes stirring to garnishing; M04 retains a peanut description after removal.'],
 ['Incomplete plan','The request is valid but the generated candidate remains incomplete, misordered or contradictory. Withholding it is protective but does not complete the request.'],
 ['False rejection','A valid request is blocked by interpretation or validation, including treating durations as ingredients or matching preparation descriptors too literally.'],
 ['Technical failure','Provider or validation execution did not complete. Three responses explicitly name RateLimitError; one consistency failure does not expose its underlying cause.'],
 ['Acceptance criteria','Zero incorrect publications; at least 95% correct first-run completion of clearly supported requests; critical regression tests pass. The live criteria were not met.'],
 ['Supported completion','Primary denominator is the 24 unique cases expected to apply. Repeats are reported separately to avoid overweighting five selected cases.'],
 ['Usage coverage',`${data.summary.recorded_planning_calls} planning-call records and ${data.summary.recorded_planning_tokens.toLocaleString('en-US')} reported planning tokens. This excludes consistency tokens and missing call records in three HTTP 502 responses. Not a full bill or dollar estimate.`],
 ['Provider limits','Late RateLimitError responses do not establish whether the cause is temporary throughput, account quota or another provider limit. Capacity needs confirmation before a retest.'],
 ['Evidence','Frozen cases.json; raw-results.json; reviewed-results.json; fault-results.json; regression-results.txt. Case IDs and run numbers identify observations.'],
 ['API source','http://127.0.0.1:8000/docs'],
 ['Recipe source','Five recipe snapshots from the application catalog: 10813, 77935, 45613, 144299, 19117.'],
 ['Limitations','Small agent-authored set, not independent human certification. This measures text-editing fidelity, not culinary quality, nutrition, food safety or production load capacity.'],
 ['Next step','Fix H01 and H02 first, then H03-H06. Diagnose O01. Add regression cases and rerun with fresh wording and repeated complex cases. Preserve this baseline.'],
 ['Automated regression','56 existing tests passed. Mocked tests do not consume API credits.'],
 ...faults.map(f=>['Fault injection: '+f.case,`Passed: ${f.passed}. HTTP ${f.http_status}; ${f.mock_calls} mock provider calls. No enhanced recipe published. Mocked through FastAPI TestClient; not a real provider outage.`]),
 ['Frozen plan SHA-256',data.plan_hash]
];
table('Method','Method and evidence','Sources, scoring definitions, limitations and controlled failure tests.', ['Item','Detail'],methods,[37,130]);
const s=base('Summary','Recipe API reliability results','24 September 2026 • 36 cases, 56 live requests • Application code unchanged',[47,19,72,3,12,15,16,16,16,14],34);
s.getRange('A4:C4').values=[['Measure','Result','Interpretation']];s.getRange('A4:C4').format={fill:blue,font:{bold:true,color:'#FFFFFF'},rowHeight:27};
const labels=[
 ['Unique cases',36,'Expected outcomes defined before testing.'],
 ['Live requests',56,'36 first runs plus 20 additional repeat runs.'],
 ['Correct first-run outcomes',null,'Includes successful edits and correct abstentions.'],
 ['Supported first-run requests',null,'Distinct requests expected to produce an enhancement.'],
 ['Correct supported first runs',null,'Actual content reviewed, not just status applied.'],
 ['Supported completion rate',null,'Acceptance target: at least 95%.'],
 ['Completion target',0.95,'Set before testing.'],
 ['Incorrect publications',null,'Zero allowed. Four observations across two defects.'],
 ['Maximum incorrect publications',0,'Set before testing.'],
 ['Incomplete plans withheld',null,'Protective rejection, but valid requests not completed.'],
 ['False rejections',null,'Valid requests blocked by classification or matching.'],
 ['Technical failures',null,'3 RateLimitError responses; 1 unavailable consistency check.'],
 ['Existing regression tests passed',56,'56 of 56 tests passed.'],
 ['Injected provider failures handled',5,'5 of 5 mocked failure tests passed.'],
 ['Recorded planning tokens',null,'Partial usage only. See Method for exclusions.'],
 ['Live acceptance criteria met',null,'Incorrect publications and completion rate both miss the target.']
];
s.getRange('A5:C20').values=labels;
const f={B7:'=COUNTIFS(\'Runs\'!B5:B60,1,\'Runs\'!E5:E60,"Correct")',B8:'=COUNTIFS(\'Runs\'!B5:B60,1,\'Runs\'!C5:C60,"applied")',B9:'=COUNTIFS(\'Runs\'!B5:B60,1,\'Runs\'!C5:C60,"applied",\'Runs\'!E5:E60,"Correct")',B10:'=B9/B8',B12:'=COUNTIF(\'Runs\'!E5:E60,"Incorrect publication")',B14:'=COUNTIF(\'Runs\'!E5:E60,"Incomplete plan")',B15:'=COUNTIF(\'Runs\'!E5:E60,"False rejection")',B16:'=COUNTIF(\'Runs\'!E5:E60,"Technical failure")',B19:"=SUM('Runs'!K5:K60)",B20:'=IF(AND(B10>=B11,B12<=B13),"Yes","No")'};
for(const [cell,formula] of Object.entries(f))s.getRange(cell).formulas=[[formula]];
s.getRange('A5:C20').format.wrapText=true;s.getRange('A5:C20').format.rowHeight=34;s.getRange('A5:C20').format.verticalAlignment='center';
s.getRange('B5:B19').setNumberFormat('#,##0');s.getRange('B10:B11').setNumberFormat('0.0%');
s.getRange('B5:B20').format.horizontalAlignment='center';
runs.getRange('L5:L60').format.horizontalAlignment='center';
s.getRange('B10').format.font={bold:true,color:'#9C2D22'};s.getRange('B12').format.font={bold:true,color:'#9C2D22'};
s.getRange('E4:J4').values=[['Case','Correct','Withheld','Incorrect','Technical','Total']];s.getRange('E4:J4').format={fill:blue,font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:27};
const repeated=first.filter(r=>r.repeat);
repeated.forEach((r,i)=>{const row=5+i;s.getRange(`E${row}`).values=[[r.id]];
 s.getRange(`F${row}:J${row}`).formulas=[[
  `=COUNTIFS('Runs'!A$5:A$60,E${row},'Runs'!E$5:E$60,"Correct")`,
  `=COUNTIFS('Runs'!A$5:A$60,E${row},'Runs'!E$5:E$60,"Incomplete plan")+COUNTIFS('Runs'!A$5:A$60,E${row},'Runs'!E$5:E$60,"False rejection")`,
  `=COUNTIFS('Runs'!A$5:A$60,E${row},'Runs'!E$5:E$60,"Incorrect publication")`,
  `=COUNTIFS('Runs'!A$5:A$60,E${row},'Runs'!E$5:E$60,"Technical failure")`,
  `=COUNTIF('Runs'!A$5:A$60,E${row})`]]; });
s.getRange('E11').values=[['Repeat results']];s.getRange('E11').format.font={bold:true};
s.getRange('E12').values=[['Only M01 completed correctly in all five runs.']];
s.getRange('E14').values=[['Fix order']];s.getRange('E14').format.font={bold:true};
s.getRange('E15').values=[['1. Published preparation and description errors (H01, H02).']];
s.getRange('E16').values=[['2. Duration, ordering and matching failures (H03-H06).']];
s.getRange('E17').values=[['3. Provider availability and actionable errors (O01).']];
s.getRange('A23').values=[['Reading this report']];s.getRange('A23').format.font={bold:true};
s.getRange('A24').values=[['Cases lists requests and expected results. Runs includes all 56 observations.']];
s.getRange('A25').values=[['Issues records severity and proposed fixes. Changes shows exact published edits.']];
s.getRange('A26').values=[['Method explains grading, usage limitations and failure-injection tests.']];
for(const name of ['Cases','Runs']){
 const sh=wb.worksheets.getItem(name), col=name==='Cases'?'H':'E', end=name==='Cases'?40:60;
 sh.getRange(`${col}5:${col}${end}`).conditionalFormats.add('containsText',{text:'Incorrect publication',format:{fill:'#FCE8E6',font:{color:'#9C2D22'}}});
 sh.getRange(`${col}5:${col}${end}`).conditionalFormats.add('containsText',{text:'False rejection',format:{fill:'#FFF3CD'}});
}
await fs.mkdir(dir,{recursive:true});
console.log((await wb.inspect({kind:'table',range:'Summary!A4:C20',include:'values,formulas',tableMaxRows:20,tableMaxCols:3,maxChars:3500})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'Formula error scan',maxChars:1000})).ndjson);
for(const [name,range] of [['Summary','A1:J26'],['Cases','A1:J7'],['Runs','A1:N7'],['Issues','A1:H11'],['Changes','A1:F7'],['Method','A1:B9']]){
 const blob=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(path.join(dir,`${name}.png`),new Uint8Array(await blob.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(dir,'Recipe_API_Reliability_Results.xlsx'));
console.log('Exported workbook');
