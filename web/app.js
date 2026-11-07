/* Standalone fully functional dashboard. Works without npm or an API key. */
const $ = (id) => document.getElementById(id);
const state = {page:'overview', overview:{}, customers:[], invoices:[], requests:[], audit:[], review:null, activeThread:null};
const money = (n) => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format((n||0)/100);
const esc = (s) => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtDate = (d) => d ? new Date(d.endsWith('Z')||d.includes('+')?d:d+'Z').toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}) : '—';
const empty = (message, icon='◇') => `<div class="empty"><span class="empty-emoji">${icon}</span>${esc(message)}</div>`;
const statusPill = (status) => `<span class="pill ${esc(status)}">${esc(status)}</span>`;
async function api(path, method='GET', body=null, token=''){
  const res=await fetch(path,{method,headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{'X-Approval-Token':token}:{})},body:body?JSON.stringify(body):undefined});
  let data;try{data=await res.json()}catch{data={detail:'Unexpected server response'}}
  if(!res.ok){const raw=data.detail;let detail=typeof raw==='string'?raw:JSON.stringify(raw||data);throw new Error(detail||`HTTP ${res.status}`)}
  return data;
}
function toast(message,error=false){const el=document.createElement('div');el.className='toast'+(error?' error':'');el.textContent=message;$('toasts').appendChild(el);setTimeout(()=>el.remove(),4700)}
function navigate(page){
  state.page=page;document.querySelectorAll('.page').forEach(el=>el.classList.toggle('active',el.id==='page-'+page));
  document.querySelectorAll('.nav-item').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
  $('breadcrumb').textContent={overview:'Overview',copilot:'AI Copilot',invoices:'Invoices',approvals:'Approval Center',customers:'Customers',audit:'Audit Trail'}[page]||page;
  window.scrollTo({top:0,behavior:'smooth'});
}
document.querySelectorAll('[data-page]').forEach(el=>el.addEventListener('click',()=>navigate(el.dataset.page)));
document.querySelectorAll('[data-go]').forEach(el=>el.addEventListener('click',()=>navigate(el.dataset.go)));
function table(headers,rows){return `<div class="scroll-table"><table><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`}
function renderOverview(){
  const o=state.overview;
  const stats=[
    {label:'Total draft value',value:money(o.draft_total_cents),sub:'Local approved drafts only',icon:'＄',color:''},
    {label:'Draft invoices',value:o.draft_invoice_count||0,sub:'Created after approval',icon:'▤',color:'green'},
    {label:'Pending approvals',value:o.pending_count||0,sub:'Awaiting human decision',icon:'◷',color:'orange'},
    {label:'Active customers',value:o.customer_count||0,sub:'Synthetic demo customers',icon:'♧',color:'purple'}];
  $('stats-grid').innerHTML=stats.map(s=>`<div class="stat-card"><div class="stat-top"><span class="stat-label">${s.label}</span><span class="stat-icon ${s.color}">${s.icon}</span></div><div class="stat-value">${s.value}</div><div class="stat-bottom">${s.sub}</div></div>`).join('');
  const totals=state.customers.map(c=>({...c,total:state.invoices.filter(i=>i.customer_id===c.id).reduce((n,i)=>n+i.amount_cents,0)}));
  const max=Math.max(...totals.map(c=>c.total),1);
  $('customer-chart').innerHTML=totals.map(c=>`<div class="bar-group"><span class="bar-label">${esc(c.name)}</span><div class="bar-track"><div class="bar-fill" style="width:${c.total/max*100}%"></div></div><span class="bar-amount">${money(c.total)}</span></div>`).join('')+(totals.every(c=>!c.total)?'<div class="empty-small">Approve a proposal to see draft volume here.</div>':'');
  const pending=state.requests.filter(r=>r.status==='pending').slice(0,3);
  $('attention-count').textContent=pending.length+' pending';
  $('attention-list').innerHTML=pending.map(r=>`<div class="attention-item"><span class="attention-icon">◷</span><div><strong>${esc(r.customer_name||'Customer')} · ${esc(r.external_reference)}</strong><small>Human review required</small></div><span class="amount">${money(r.amount_cents)}</span></div>`).join('') || '<div class="empty-small">No pending proposals. You’re all caught up.</div>';
  $('recent-activity').innerHTML=state.audit.length?table(['Event','Reference / Details','When'],state.audit.slice(0,5).map(a=>`<tr><td class="td-strong">${esc(a.action.replaceAll('_',' '))}</td><td>${esc(a.detail)}</td><td>${fmtDate(a.created_at)}</td></tr>`)):empty('No activity yet. Submit a proposal to get started.');
}
function renderInvoices(){
  $('invoice-count').textContent=state.invoices.length+' records';
  $('invoice-table').innerHTML=state.invoices.length?table(['Invoice','Customer','Description','Amount','Status','Created'],state.invoices.map(i=>`<tr><td class="td-strong">${esc(i.external_reference)}<span class="td-secondary">#${i.id}</span></td><td>${esc(i.customer_name)}</td><td>${esc(i.description)}</td><td class="td-strong">${money(i.amount_cents)}</td><td>${statusPill(i.status)}</td><td>${fmtDate(i.created_at)}</td></tr>`)):empty('No invoice drafts. Only approved proposals appear here.','▤');
}
function renderApprovals(){
  const p=state.requests.filter(r=>r.status==='pending');$('pending-count').textContent=p.length+' pending';$('nav-pending').textContent=p.length;
  $('pending-table').innerHTML=p.length?table(['Reference','Customer','Amount','Description','Decision'],p.map(r=>`<tr><td class="td-strong">${esc(r.external_reference)}</td><td>${esc(r.customer_name)}</td><td class="td-strong">${money(r.amount_cents)}</td><td>${esc(r.description)}</td><td><div class="action-row"><button class="mini-button approve" data-review="${r.id}" data-decision="approve">Approve</button><button class="mini-button reject" data-review="${r.id}" data-decision="reject">Reject</button></div></td></tr>`)):empty('No proposals awaiting review.','✓');
}
function renderCustomers(){
  $('customers-grid').innerHTML=state.customers.map(c=>`<article class="panel customer-card"><div class="customer-avatar">${esc(c.name.split(' ').map(s=>s[0]).slice(0,2).join(''))}</div><h3>${esc(c.name)}</h3><p>Customer ID ${c.id} · Synthetic test record</p></article>`).join('');
  $('draft-customer').innerHTML=state.customers.map(c=>`<option value="${c.id}">${esc(c.name)}</option>`).join('');
}
function renderAudit(){
  $('audit-table').innerHTML=state.audit.length?table(['Event ID','Action','Proposal','Reference','Date'],state.audit.map(a=>`<tr><td class="td-strong">#${a.id}</td><td>${esc(a.action.replaceAll('_',' '))}</td><td>#${a.entity_id}</td><td>${esc(a.detail)}</td><td>${fmtDate(a.created_at)}</td></tr>`)):empty('No audit events recorded yet.','☷');
}
async function refresh(){
  try{
    const [overview,customers,invoices,requests,audit,health]=await Promise.all([api('/overview'),api('/customers'),api('/invoices'),api('/requests'),api('/audit'),api('/health')]);
    Object.assign(state,{overview,customers,invoices,requests,audit});
    const real=health.agent_mode==='openai_langgraph';$('mode-status').textContent=real?'✦ OpenAI + LangGraph':'◈ Offline demo mode';
    $('agent-tagline').textContent=real?'Live LLM · LangGraph tool orchestration':'Deterministic demonstration · no live LLM';
    renderOverview();renderInvoices();renderApprovals();renderCustomers();renderAudit();
  }catch(e){toast('Could not load backend: '+e.message,true)}
}
$('refresh').addEventListener('click',()=>{refresh().then(()=>toast('Data refreshed'))});$('refresh-audit').addEventListener('click',()=>refresh());
$('new-invoice').addEventListener('click',()=>$('create-modal').showModal());
document.querySelectorAll('[data-close]').forEach(el=>el.addEventListener('click',()=>el.closest('dialog').close()));
$('create-form').addEventListener('submit',async(e)=>{
  e.preventDefault();const f=e.target;const amount=Math.round(Number($('draft-amount').value)*100);
  const key='form-'+(globalThis.crypto?.randomUUID?.()||Date.now()+'-'+Math.random()).toString();
  try{const result=await api('/requests','POST',{customer_id:Number($('draft-customer').value),amount_cents:amount,
    description:$('draft-desc').value.trim(),external_reference:$('draft-ref').value.trim(),idempotency_key:key});
    $('create-modal').close();f.reset();toast('Proposal #'+result.id+' created. Human approval required.');await refresh();navigate('approvals');
  }catch(err){toast(err.message,true)}
});
function openReview(id,decision,threadId=null){
  const r=state.requests.find(item=>item.id===Number(id));if(!r){toast('Proposal not found; refresh and try again',true);return}
  state.review={id:Number(id),decision,threadId};$('review-title').textContent=(decision==='approve'?'Approve':'Reject')+' proposal #'+id;
  $('review-details').innerHTML=`<div><strong>Customer:</strong> ${esc(r.customer_name)}</div><div><strong>Reference:</strong> ${esc(r.external_reference)}</div><div><strong>Amount:</strong> ${money(r.amount_cents)}</div><div><strong>Work:</strong> ${esc(r.description)}</div><div><strong>Action:</strong> ${decision==='approve'?'Create exactly one local draft invoice':'Reject without creating an invoice'}</div>`;
  $('confirm-review').textContent=decision==='approve'?'Approve & create draft':'Reject proposal';$('review-token').value='';$('review-modal').showModal();$('review-token').focus();
}
document.addEventListener('click',(e)=>{const target=e.target.closest('[data-review]');if(target)openReview(target.dataset.review,target.dataset.decision,target.dataset.thread||null)});
$('review-form').addEventListener('submit',async(e)=>{
  e.preventDefault();if(!state.review)return;const {id,decision,threadId}=state.review;
  const token=$('review-token').value;
  $('confirm-review').disabled=true;
  try{const data=await api(threadId?`/agent/threads/${encodeURIComponent(threadId)}/decision`:`/requests/${id}/decision`,'POST',{decision},token);
    $('review-modal').close();toast(decision==='approve'?'Local invoice draft created':'Proposal rejected');
    if(threadId){addBubble('bot',data.answer);renderTrace(data.trace)}
    await refresh();
  }catch(err){toast(err.message,true)}finally{$('confirm-review').disabled=false;$('review-token').value=''}
});
function addBubble(who,message,pending=null){
  const container=$('chat-history');const welcome=container.querySelector('.welcome-chat');if(welcome)welcome.remove();
  const bubble=document.createElement('div');bubble.className='chat-bubble '+who;
  bubble.innerHTML=`<span class="bubble-label">${who==='user'?'YOU':'COPILOT'}</span>${esc(message)}`;
  container.appendChild(bubble);
  if(pending){
    const bar=document.createElement('div');bar.className='chat-bubble bot';bar.innerHTML=`<strong>Review required · Proposal #${pending.request_id}</strong><div class="action-row" style="margin-top:10px"><button class="mini-button approve" data-review="${pending.request_id}" data-decision="approve" data-thread="${esc(pending.thread_id)}">Approve</button><button class="mini-button reject" data-review="${pending.request_id}" data-decision="reject" data-thread="${esc(pending.thread_id)}">Reject</button></div>`;
    container.appendChild(bar);
  }
  container.scrollTop=container.scrollHeight;
}
function renderTrace(trace){
  $('tool-trace').innerHTML=trace?.length?trace.map((t,i)=>`<div class="trace-item"><div class="trace-title"><span class="trace-icon">✓</span> ${i+1}. ${esc(t.tool.replaceAll('_',' '))}</div><div class="trace-result">${esc(t.error||((t.result?.error)?t.result.error:'Executed · '+(t.result?.status||'OK')))}</div></div>`).join(''):'<div class="empty-small">No tools were called.</div>';
}
async function sendChat(message){
  const input=$('chat-input');const btn=$('send-button');if(!message.trim())return;
  input.value='';addBubble('user',message);btn.disabled=true;btn.textContent='Working…';
  try{const data=await api('/agent/chat','POST',{message});addBubble('bot',data.answer,data.status==='pending_approval'?data:null);renderTrace(data.trace);await refresh();}
  catch(err){addBubble('bot','Request failed: '+err.message);toast(err.message,true)}
  finally{btn.disabled=false;btn.textContent='Send ↗'}
}
$('chat-form').addEventListener('submit',(e)=>{e.preventDefault();sendChat($('chat-input').value)});
$('chat-input').addEventListener('keydown',(e)=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('chat-form').requestSubmit()}});
document.querySelectorAll('[data-prompt]').forEach(el=>el.addEventListener('click',()=>sendChat(el.dataset.prompt)));
$('sample-prompt').addEventListener('click',()=>{$('chat-input').value='Prepare invoice for Acme Corp, $2,500, description: Consulting services, reference INV-1005.';$('chat-input').focus()});
refresh();
