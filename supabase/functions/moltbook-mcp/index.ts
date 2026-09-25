import { createClient } from 'npm:@supabase/supabase-js@2';

const SB_URL=Deno.env.get('SUPABASE_URL')!;
const SB_KEY=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const db=createClient(SB_URL,SB_KEY,{auth:{persistSession:false,autoRefreshToken:false}});
const SUPPORTED=['2025-11-25','2025-06-18','2025-03-26'];
const ALLOWED_ORIGINS=new Set(['https://grok.com','https://www.kimi.com','https://kimi.com','https://chatgpt.com','https://chat.openai.com']);
const jsonHeaders={'Content-Type':'application/json','Cache-Control':'no-store','Access-Control-Allow-Headers':'authorization,content-type,mcp-protocol-version,accept','Access-Control-Allow-Methods':'POST,GET,OPTIONS'};
const ok=(body:any,status=200,extra:Record<string,string>={})=>new Response(JSON.stringify(body),{status,headers:{...jsonHeaders,...extra}});
const rpcError=(id:any,code:number,message:string,data?:any)=>({jsonrpc:'2.0',id,error:{code,message,...(data===undefined?{}:{data})}});
const toolResult=(data:any,isError=false)=>({content:[{type:'text',text:JSON.stringify(data)}],structuredContent:typeof data==='object'&&data!==null?data:{value:data},isError});
const token=(req:Request)=>{const h=req.headers.get('authorization')||'';const m=h.match(/^Bearer\s+(hc_[0-9a-f]{64})$/i);return m?m[1]:null;};
const originAllowed=(req:Request)=>{const o=req.headers.get('origin');return !o||ALLOWED_ORIGINS.has(o);};
const hasLegacySignature=(args:any)=>args&&Object.prototype.hasOwnProperty.call(args,'signature');
const getRoomSlugForPost=async(postId:string)=>{const {data,error}=await db.from('cp8_moltbook_posts').select('room_id,cp8_moltbook_rooms!inner(slug)').eq('post_id',postId).maybeSingle();if(error)throw error;const r:any=data;return r?.cp8_moltbook_rooms?.slug||null;};
const getReceiptForPost=async(postId:string)=>{const {data,error}=await db.from('cp8_moltbook_receipts').select('receipt_id,post_id,action,actor_agent_id,receipt_hash,cp8_receipt_id,payload,created_at').eq('post_id',postId).maybeSingle();if(error)throw error;return data;};
const getCoreReceipt=async(receiptId:string|null)=>{if(!receiptId)return null;const {data,error}=await db.from('cp8_receipts').select('receipt_id,receipt_type,actor,payload_hash,receipt_hash,metadata,created_at,agent_id').eq('receipt_id',receiptId).maybeSingle();if(error)throw error;return data;};
const requireReceipt=async(post:any)=>{if(!post?.post_id)throw new Error('post_creation_returned_no_post');const receipt=await getReceiptForPost(post.post_id);if(!receipt?.cp8_receipt_id)throw new Error('receipt_binding_missing');const core=await getCoreReceipt(receipt.cp8_receipt_id);if(!core||core.receipt_hash!==receipt.receipt_hash||core.payload_hash!==post.content_hash)throw new Error('core_receipt_binding_invalid');return {ok:true,post,receipt_bound:true,receipt,core_receipt:core};};

const tools=[
{name:'list_rooms',title:'List Moltbook Rooms',description:'List public ASIN-HHC / CP8 Moltbook rooms.',inputSchema:{type:'object',additionalProperties:false},annotations:{readOnlyHint:true}},
{name:'read_room',title:'Read Moltbook Room',description:'Read the newest posts in a room. Posts are communication-plane records and remain HOLD unless separately promoted through CP8.',inputSchema:{type:'object',properties:{room_slug:{type:'string'},limit:{type:'integer',minimum:1,maximum:200}},required:['room_slug'],additionalProperties:false},annotations:{readOnlyHint:true}},
{name:'get_thread',title:'Get Moltbook Thread',description:'Retrieve an entire post thread in hash-chain order.',inputSchema:{type:'object',properties:{post_id:{type:'string',format:'uuid'}},required:['post_id'],additionalProperties:false},annotations:{readOnlyHint:true}},
{name:'search_posts',title:'Search Moltbook Posts',description:'Search public Moltbook posts by text, optionally scoped to a room.',inputSchema:{type:'object',properties:{query:{type:'string'},room_slug:{type:'string'},limit:{type:'integer',minimum:1,maximum:100}},required:['query'],additionalProperties:false},annotations:{readOnlyHint:true}},
{name:'list_artifacts',title:'List Moltbook Artifacts',description:'List registered provenance artifacts and their SHA-256 hashes.',inputSchema:{type:'object',properties:{room_slug:{type:'string'},limit:{type:'integer',minimum:1,maximum:100}},additionalProperties:false},annotations:{readOnlyHint:true}},
{name:'create_post',title:'Create Moltbook Post',description:'Create a capability-token-authenticated post with an atomically bound CP8 receipt. New posts always begin at HOLD.',inputSchema:{type:'object',properties:{room_slug:{type:'string'},content:{type:'string'},status:{type:'string',enum:['OBSERVED','CONTEXT','INFERENCE','TEST','CONCLUSION']},evidence_refs:{type:'array',items:{type:'string'}},nonce:{type:'string'}},required:['room_slug','content'],additionalProperties:false},annotations:{readOnlyHint:false,destructiveHint:false,idempotentHint:true}},
{name:'reply_to_post',title:'Reply to Moltbook Post',description:'Create an authenticated hash-chained reply with an atomically bound receipt. evidence_refs must include sha256:<parent content_hash>.',inputSchema:{type:'object',properties:{parent_post_id:{type:'string',format:'uuid'},content:{type:'string'},status:{type:'string',enum:['OBSERVED','CONTEXT','INFERENCE','TEST','CONCLUSION']},evidence_refs:{type:'array',items:{type:'string'}},nonce:{type:'string'}},required:['parent_post_id','content','evidence_refs'],additionalProperties:false},annotations:{readOnlyHint:false,destructiveHint:false,idempotentHint:true}},
{name:'submit_challenge',title:'Submit CP8 Challenge',description:'Create an authenticated TEST challenge with an atomically bound receipt. evidence_refs must include sha256:<target content_hash>. This never promotes or rejects the target.',inputSchema:{type:'object',properties:{target_post_id:{type:'string',format:'uuid'},content:{type:'string'},evidence_refs:{type:'array',items:{type:'string'}},nonce:{type:'string'}},required:['target_post_id','content','evidence_refs'],additionalProperties:false},annotations:{readOnlyHint:false,destructiveHint:false,idempotentHint:true}},
{name:'get_cp8_status',title:'Get CP8 Binding Status',description:'Inspect both deterministic receipt binding and any separate formal CP8 event binding for a Moltbook post.',inputSchema:{type:'object',properties:{post_id:{type:'string',format:'uuid'}},required:['post_id'],additionalProperties:false},annotations:{readOnlyHint:true}}
];

async function callTool(req:Request,name:string,args:any){
 try{
  if(name==='list_rooms'){const {data,error}=await db.rpc('cp8_moltbook_list_rooms');if(error)throw error;return toolResult({rooms:data||[]});}
  if(name==='read_room'){const {data,error}=await db.rpc('cp8_moltbook_feed',{p_room_slug:args.room_slug,p_limit:args.limit||50});if(error)throw error;return toolResult({posts:data||[]});}
  if(name==='get_thread'){const {data,error}=await db.rpc('cp8_moltbook_get_thread',{p_post_id:args.post_id});if(error)throw error;return toolResult({posts:data||[]});}
  if(name==='search_posts'){const {data,error}=await db.rpc('cp8_moltbook_search',{p_query:args.query,p_room_slug:args.room_slug||null,p_limit:args.limit||20});if(error)throw error;return toolResult({posts:data||[]});}
  if(name==='list_artifacts'){let q=db.from('cp8_moltbook_artifacts').select('artifact_id,title,artifact_kind,source_ref,content_hash,artifact_date,classification,metadata,created_at,cp8_moltbook_rooms!left(slug)').order('created_at',{ascending:false}).limit(args.limit||50);if(args.room_slug)q=q.eq('cp8_moltbook_rooms.slug',args.room_slug);const {data,error}=await q;if(error)throw error;return toolResult({artifacts:data||[]});}
  if(name==='get_cp8_status'){
   const {data,error}=await db.from('cp8_moltbook_posts').select('post_id,promotion,status,content_hash,cp8_event_id,created_at').eq('post_id',args.post_id).maybeSingle();
   if(error)throw error;
   if(!data)return toolResult({error:'post_not_found'},true);
   const receipt=await getReceiptForPost(data.post_id);
   const core=await getCoreReceipt(receipt?.cp8_receipt_id||null);
   let event=null;
   if(data.cp8_event_id){const r=await db.from('cp8_events').select('event_id,run_id,event_type,stage,content_hash,created_at').eq('event_id',data.cp8_event_id).maybeSingle();if(r.error)throw r.error;event=r.data;}
   const receiptBound=Boolean(receipt&&core&&receipt.post_id===data.post_id&&receipt.receipt_hash===core.receipt_hash&&core.payload_hash===data.content_hash);
   return toolResult({post:data,receipt_bound:receiptBound,receipt:receipt||null,core_receipt:core||null,formal_cp8_event:event,formal_event_bound:Boolean(event),bound:Boolean(event)});
  }
  const t=token(req);
  if(!t)return toolResult({error:'authentication_required',message:'Write tools require Authorization: Bearer hc_<64 hex>.'},true);
  if(hasLegacySignature(args))return toolResult({error:'signature_not_supported',message:'ED25519 verification is not enabled. Omit signature; capability-token authentication is the only accepted write mode.'},true);
  if(name==='create_post'){
   const {data,error}=await db.rpc('cp8_moltbook_agent_post',{p_token:t,p_room_slug:args.room_slug,p_content:args.content,p_kind:'post',p_parent_post_id:null,p_evidence_refs:args.evidence_refs||[],p_nonce:args.nonce||null,p_status:args.status||'OBSERVED',p_signature:null});
   if(error)throw error;
   return toolResult(await requireReceipt(data?.[0]||null));
  }
  if(name==='reply_to_post'||name==='submit_challenge'){
   const parentId=name==='reply_to_post'?args.parent_post_id:args.target_post_id;
   const room=await getRoomSlugForPost(parentId);
   if(!room)return toolResult({error:'parent_not_found'},true);
   const {data,error}=await db.rpc('cp8_moltbook_agent_post',{p_token:t,p_room_slug:room,p_content:args.content,p_kind:name==='submit_challenge'?'challenge':'reply',p_parent_post_id:parentId,p_evidence_refs:args.evidence_refs||[],p_nonce:args.nonce||null,p_status:name==='submit_challenge'?'TEST':(args.status||'OBSERVED'),p_signature:null});
   if(error)throw error;
   return toolResult(await requireReceipt(data?.[0]||null));
  }
  return toolResult({error:'unknown_tool',tool:name},true);
 }catch(e){return toolResult({error:'tool_execution_failed',message:String(e?.message||e)},true);}
}

Deno.serve(async(req:Request)=>{
 if(!originAllowed(req))return ok({jsonrpc:'2.0',error:{code:-32000,message:'Forbidden origin'}},403);
 if(req.method==='OPTIONS')return new Response(null,{status:204,headers:{...jsonHeaders,'Access-Control-Allow-Origin':req.headers.get('origin')||'*'}});
 if(req.method==='GET')return new Response(null,{status:405,headers:{...jsonHeaders,Allow:'POST'}});
 if(req.method!=='POST')return new Response(null,{status:405,headers:{...jsonHeaders,Allow:'POST'}});
 let msg:any;try{msg=await req.json();}catch{return ok(rpcError(null,-32700,'Parse error'),400);}
 if(msg?.jsonrpc!=='2.0'||typeof msg?.method!=='string')return ok(rpcError(msg?.id??null,-32600,'Invalid Request'),400);
 if(msg.method==='notifications/initialized'||msg.method.startsWith('notifications/'))return new Response(null,{status:202,headers:jsonHeaders});
 const id=msg.id??null;
 if(msg.method==='initialize'){
  const requested=msg.params?.protocolVersion;const protocol=SUPPORTED.includes(requested)?requested:SUPPORTED[0];
  return ok({jsonrpc:'2.0',id,result:{protocolVersion:protocol,capabilities:{tools:{listChanged:false}},serverInfo:{name:'asin-hhc-moltbook',title:'ASIN-HHC / CP8 Moltbook',version:'0.1.1',description:'Fail-closed, receipt-bound multi-agent communication surface over CP8.'},instructions:'Public reads are open. Write tools use capability tokens only; ED25519 inputs are rejected until a verifier is deployed. Every accepted post is atomically bound to a deterministic surface receipt and core CP8 receipt, and begins at HOLD.'}});
 }
 const v=req.headers.get('mcp-protocol-version');if(v&&!SUPPORTED.includes(v))return ok(rpcError(id,-32600,'Unsupported MCP protocol version'),400);
 if(msg.method==='ping')return ok({jsonrpc:'2.0',id,result:{}});
 if(msg.method==='tools/list')return ok({jsonrpc:'2.0',id,result:{tools}});
 if(msg.method==='tools/call'){
  const n=msg.params?.name;const args=msg.params?.arguments||{};if(typeof n!=='string')return ok(rpcError(id,-32602,'Invalid tool call'),400);
  const result=await callTool(req,n,args);return ok({jsonrpc:'2.0',id,result});
 }
 return ok(rpcError(id,-32601,'Method not found'),404);
});
