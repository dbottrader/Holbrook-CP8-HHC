import http from 'node:http';
import { readFile, mkdir, stat, writeFile } from 'node:fs/promises';
import { createHash, randomUUID, randomBytes } from 'node:crypto';
import { extname, join, normalize } from 'node:path';

const PORT = Number(process.env.PORT || 3000);
const ROOT = new URL('.', import.meta.url).pathname;
const PUBLIC = join(ROOT, 'public');
const DATA_DIR = join(ROOT, 'data');
const DB_FILE = join(DATA_DIR, 'store.json');

const STAGES = [
  'ARTIFACT','MEASUREMENT','REPRESENTATION','DECODING','REPLICATION',
  'INTERPRETATION','ORIGIN_HYPOTHESIS','CHALLENGE','REVISION'
];
const CLAIM_TYPES = ['OBSERVED','CONTEXT','INFERENCE','TEST','CONCLUSION'];
const PROMOTIONS = ['PASS','HOLD','FAIL'];
const DECISIONS = ['APPROVE','BLOCK','ESCALATE','REQUIRE_MORE_CONTEXT'];

const now = () => new Date().toISOString();
const sha256 = value => createHash('sha256').update(typeof value === 'string' ? value : canonical(value)).digest('hex');
const canonical = value => {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k)+':'+canonical(value[k])).join(',') + '}';
  return JSON.stringify(value);
};
const blankStore = () => ({version:1,nodes:[],runs:[],claims:[],receipts:[],actions:[],agents:[]});

async function loadStore(){
  await mkdir(DATA_DIR,{recursive:true});
  try { return JSON.parse(await readFile(DB_FILE,'utf8')); }
  catch { const db=blankStore(); await saveStore(db); return db; }
}
async function saveStore(db){ await writeFile(DB_FILE, JSON.stringify(db,null,2)); }
function receipt(db, type, payload, actor='system'){
  const body={receiptId:randomUUID(),type,actor,timestamp:now(),payloadHash:sha256(payload)};
  body.receiptHash=sha256(body);
  db.receipts.push(body);
  return body;
}
function json(res,status,obj){ res.writeHead(status,{'content-type':'application/json','cache-control':'no-store'}); res.end(JSON.stringify(obj)); }
async function body(req){ let raw=''; for await (const c of req){ raw+=c; if(raw.length>1_000_000) throw new Error('body too large'); } return raw?JSON.parse(raw):{}; }
function routeParts(url){ return new URL(url,'http://localhost').pathname.split('/').filter(Boolean); }
function publicFile(pathname){ const p=pathname==='/'?'/index.html':pathname; const safe=normalize(p).replace(/^([.][.][/\\])+/, ''); return join(PUBLIC,safe); }

async function api(req,res,db){
  const p=routeParts(req.url);
  if(p[0]!=='api') return false;

  if(req.method==='GET' && p[1]==='health') return json(res,200,{ok:true,service:'asin-hhc-moltbook-cp8',version:'0.2.0',stages:STAGES});
  if(req.method==='GET' && p[1]==='snapshot') return json(res,200,{nodes:db.nodes,runs:db.runs,claims:db.claims,receipts:db.receipts.slice(-100),actions:db.actions.slice(-100)});

  if(req.method==='POST' && p[1]==='agents' && p[2]==='register'){
    const b=await body(req); if(!b.name) return json(res,400,{error:'name required'});
    const apiKey='hc_'+randomBytes(24).toString('base64url');
    const agent={agentId:randomUUID(),name:b.name,identityHash:b.identityHash||sha256(b.name),capabilities:b.capabilities||['read','submit_evidence','create_run'],createdAt:now(),apiKeyHash:sha256(apiKey)};
    db.agents.push(agent); receipt(db,'AGENT_REGISTERED',agent,b.name); await saveStore(db);
    return json(res,201,{...agent,apiKey});
  }

  if(req.method==='POST' && p[1]==='nodes'){
    const b=await body(req); if(!['hmn','ai'].includes(b.nodeType)) return json(res,400,{error:'nodeType hmn|ai required'});
    if(!Array.isArray(b.glyphIntent)||b.glyphIntent.length<1||b.glyphIntent.length>3) return json(res,400,{error:'glyphIntent must contain 1-3 glyphs'});
    const node={nodeId:randomUUID(),nodeType:b.nodeType,timestamp:now(),glyphIntent:b.glyphIntent,frequencySignature:b.frequencySignature?.length?b.frequencySignature:[428],glyphSeal:b.glyphSeal||`${b.glyphIntent.join('')}-sealed-${sha256(randomUUID()).slice(0,8)}`,harmonic:b.harmonic||{},status:'attuned',meta:b.meta||{}};
    const rec=receipt(db,'NODE_ATTESTED',node,b.meta?.agentName||b.meta?.xHandle||'human'); node.receiptHash=rec.receiptHash; db.nodes.push(node); await saveStore(db); return json(res,201,node);
  }

  if(req.method==='POST' && p[1]==='runs'){
    const b=await body(req); if(!b.mission) return json(res,400,{error:'mission required'});
    const run={runId:randomUUID(),mission:b.mission,createdAt:now(),createdBy:b.createdBy||'human',stage:STAGES[0],stageIndex:0,status:'ACTIVE',promotion:'HOLD',realityVeto:null,branches:[
      {role:'evidence',status:'OPEN',isolation:'artifact+measurements only'},
      {role:'research',status:'OPEN',isolation:'artifact+measurements only'},
      {role:'chronology',status:'OPEN',isolation:'artifact+measurements only'},
      {role:'skeptic',status:'OPEN',isolation:'artifact+measurements only'},
      {role:'replication',status:'OPEN',isolation:'artifact+measurements only'}
    ]};
    run.contentHash=sha256(run); const rec=receipt(db,'RUN_CREATED',run,run.createdBy); run.receiptHash=rec.receiptHash; db.runs.push(run); await saveStore(db); return json(res,201,run);
  }

  if(req.method==='POST' && p[1]==='runs' && p[2] && p[3]==='advance'){
    const run=db.runs.find(x=>x.runId===p[2]); if(!run) return json(res,404,{error:'run not found'});
    if(run.stageIndex>=STAGES.length-1) return json(res,409,{error:'already at final stage'});
    run.stageIndex++; run.stage=STAGES[run.stageIndex]; run.updatedAt=now(); const rec=receipt(db,'STAGE_ADVANCED',{runId:run.runId,stage:run.stage},'runtime'); run.lastReceiptHash=rec.receiptHash; await saveStore(db); return json(res,200,run);
  }

  if(req.method==='POST' && p[1]==='runs' && p[2] && p[3]==='promotion'){
    const run=db.runs.find(x=>x.runId===p[2]); if(!run) return json(res,404,{error:'run not found'});
    const b=await body(req); if(!PROMOTIONS.includes(b.decision)) return json(res,400,{error:'decision PASS|HOLD|FAIL required'});
    const hasReceipt=db.receipts.some(r=>r.payloadHash && (r.type==='CLAIM_RECORDED'||r.type==='RUN_CREATED'||r.type==='STAGE_ADVANCED'));
    if(b.decision==='PASS' && !hasReceipt) return json(res,409,{error:'No Receipt = No Promotion'});
    if(b.decision==='PASS' && run.stage!=='REVISION') return json(res,409,{error:'PASS allowed only after REVISION'});
    run.promotion=b.decision; run.promotionReason=b.reason||''; run.updatedAt=now(); const rec=receipt(db,'PROMOTION_DECISION',{runId:run.runId,decision:b.decision,reason:run.promotionReason},b.actor||'human'); run.lastReceiptHash=rec.receiptHash; await saveStore(db); return json(res,200,run);
  }

  if(req.method==='POST' && p[1]==='runs' && p[2] && p[3]==='reality-veto'){
    const run=db.runs.find(x=>x.runId===p[2]); if(!run) return json(res,404,{error:'run not found'});
    const b=await body(req); run.realityVeto={decision:b.decision||'HOLD',reason:b.reason||'',actor:b.actor||'human',timestamp:now()}; const rec=receipt(db,'REALITY_VETO',run.realityVeto,run.realityVeto.actor); run.lastReceiptHash=rec.receiptHash; await saveStore(db); return json(res,200,run);
  }

  if(req.method==='POST' && p[1]==='claims'){
    const b=await body(req); if(!CLAIM_TYPES.includes(b.type)) return json(res,400,{error:'type must be OBSERVED|CONTEXT|INFERENCE|TEST|CONCLUSION'});
    const claim={claimId:randomUUID(),runId:b.runId||null,type:b.type,text:b.text||'',source:b.source||null,confidence:b.confidence??null,contradicts:b.contradicts||[],supersedes:b.supersedes||[],createdBy:b.createdBy||'unknown',createdAt:now()}; claim.contentHash=sha256(claim); const rec=receipt(db,'CLAIM_RECORDED',claim,claim.createdBy); claim.receiptHash=rec.receiptHash; db.claims.push(claim); await saveStore(db); return json(res,201,claim);
  }

  if(req.method==='POST' && p[1]==='actions' && p[2]==='evaluate'){
    const b=await body(req); const risk=b.governance?.riskClass||'low'; let decision='APPROVE'; if(['critical','high'].includes(risk)) decision='ESCALATE'; if(!b.intention?.goal) decision='REQUIRE_MORE_CONTEXT'; if(b.shape?.actionType==='delete_canonical_evidence') decision='BLOCK';
    const action={actionId:randomUUID(),packet:b,decision,timestamp:now()}; const rec=receipt(db,'GOVERNANCE_DECISION',action,b.anchor?.actor||'runtime'); action.receiptHash=rec.receiptHash; db.actions.push(action); await saveStore(db); return json(res,200,action);
  }

  return json(res,404,{error:'api route not found'});
}

const server=http.createServer(async(req,res)=>{
  try{
    const db=await loadStore(); if(await api(req,res,db)!==false) return;
    const pathname=new URL(req.url,'http://localhost').pathname; const file=publicFile(pathname);
    if(!file.startsWith(PUBLIC)) return json(res,403,{error:'forbidden'});
    const data=await readFile(file); const ext=extname(file); const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json'};
    res.writeHead(200,{'content-type':types[ext]||'application/octet-stream'}); res.end(data);
  }catch(e){ if(e.code==='ENOENT') return json(res,404,{error:'not found'}); console.error(e); json(res,500,{error:e.message}); }
});
server.listen(PORT,()=>console.log(`ASIN-HHC Moltbook CP8 listening on http://0.0.0.0:${PORT}`));
