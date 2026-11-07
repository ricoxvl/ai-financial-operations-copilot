import React, {useCallback, useEffect, useRef, useState} from 'react';

/* React/Vite version of the fully-working no-build dashboard served by FastAPI at /. */
const money=n=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format((n||0)/100);
const stamp=s=>s?new Date(s.endsWith('Z')||s.includes('+')?s:s+'Z').toLocaleDateString():'—';
async function api(url,method='GET',body,token){
  const response=await fetch(url,{method,headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{'X-Approval-Token':token}:{})},body:body?JSON.stringify(body):undefined});
  const data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data));
  return data;
}
const sections=[['overview','▦','Overview'],['copilot','✦','AI Copilot'],['invoices','▤','Invoices'],['approvals','⛨','Approvals'],['customers','♧','Customers'],['audit','☷','Audit Trail']];
const Empty=({children})=><div className="empty"><span className="empty-emoji">◇</span>{children}</div>;
const Pill=({text})=><span className={'pill '+text}>{text}</span>;
function DataTable({headers,rows}){return rows.length?<div style={{overflowX:'auto'}}><table><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows}</tbody></table></div>:<Empty>No records to display yet.</Empty>}
function SectionHead({eyebrow,title,subtitle,action}){return <div className="page-head"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="subtitle">{subtitle}</p></div>{action}</div>}

export default function App(){
  const [page,setPage]=useState('overview');
  const [data,setData]=useState({overview:{},customers:[],requests:[],invoices:[],audit:[],health:{}});
  const [notice,setNotice]=useState('');const [review,setReview]=useState(null);const [modal,setModal]=useState(false);
  const [approvalToken,setApprovalToken]=useState('');const [draft,setDraft]=useState({customer_id:'',amount:'',description:'',external_reference:''});
  const [messages,setMessages]=useState([]);const [prompt,setPrompt]=useState('');const [sending,setSending]=useState(false);const [trace,setTrace]=useState([]);
  const chatBottom=useRef(null);
  const notify=(message)=>{setNotice(message);window.setTimeout(()=>setNotice(''),5000)};
  const refresh=useCallback(async()=>{
    try{const [overview,customers,requests,invoices,audit,health]=await Promise.all(['/overview','/customers','/requests','/invoices','/audit','/health'].map(path=>api(path)));
      setData({overview,customers,requests,invoices,audit,health});
    }catch(e){notify('Backend connection failed: '+e.message)}
  },[]);
  useEffect(()=>{refresh()},[refresh]);
  useEffect(()=>chatBottom.current?.scrollIntoView({behavior:'smooth',block:'nearest'}),[messages]);
  const pending=data.requests.filter(r=>r.status==='pending');
  const send=async(text=prompt)=>{
    if(!text.trim()||sending)return;setPrompt('');setMessages(old=>[...old,{who:'user',text}]);setSending(true);
    try{const response=await api('/agent/chat','POST',{message:text});setMessages(old=>[...old,{who:'bot',text:response.answer,pending:response.status==='pending_approval'?response:null}]);setTrace(response.trace);await refresh()}
    catch(e){setMessages(old=>[...old,{who:'bot',text:'Error: '+e.message}])}
    finally{setSending(false)}
  };
  const decide=async(e)=>{
    e.preventDefault();if(!review)return;
    try{const url=review.thread_id?`/agent/threads/${review.thread_id}/decision`:`/requests/${review.id}/decision`;
      const result=await api(url,'POST',{decision:review.decision},approvalToken);
      if(review.thread_id)setMessages(old=>[...old,{who:'bot',text:result.answer}]);
      setTrace(result.trace||trace);setReview(null);notify('Decision recorded.');await refresh();
    }catch(e){notify('Review failed: '+e.message)}finally{setApprovalToken('')}
  };
  const create=async(e)=>{
    e.preventDefault();
    try{await api('/requests','POST',{customer_id:Number(draft.customer_id||data.customers[0]?.id),
      amount_cents:Math.round(Number(draft.amount)*100),description:draft.description,
      external_reference:draft.external_reference,idempotency_key:'react-'+crypto.randomUUID()});
      setModal(false);setDraft({customer_id:'',amount:'',description:'',external_reference:''});notify('Pending proposal created.');await refresh();setPage('approvals');
    }catch(e){notify('Could not create proposal: '+e.message)}
  };
  const reviewFor=(r,decision,thread_id)=>setReview({id:r.id,decision,thread_id,request:r});
  const headline = data.health.agent_mode==='openai_langgraph'?'✦ Live AI + LangGraph':'◈ Offline demo';
  const navBtn=(p)=><button className="primary-button" onClick={()=>setPage(p)}>✦ &nbsp;Ask copilot</button>;
  return <div className="shell">
    <aside className="sidebar"><div className="logo"><div className="logo-symbol">◈</div>finpilot<span className="logo-dot">.</span></div><div className="workspace-label">WORKSPACE <span>DEMO</span></div><nav>
      {sections.map(([id,icon,label])=><button key={id} className={'nav-item '+(page===id?'active':'')} onClick={()=>setPage(id)}><span className="nav-icon">{icon}</span>{label}{id==='approvals'&&<span className="count-pill">{pending.length}</span>}</button>)}
    </nav><div className="sidebar-bottom"><div className="sandbox"><div className="sandbox-title"><span className="pulse-dot"/>Sandbox Environment</div><p>All data is synthetic. No real accounts or payments.</p></div><div className="user-mini"><div className="avatar">FP</div><div><strong>Demo workspace</strong><small>Financial operations</small></div></div></div></aside>
    <main className="main"><header className="topbar"><div className="crumbs">Workspace <span className="chevron">›</span><strong>{sections.find(s=>s[0]===page)?.[2]}</strong></div><div className="top-actions"><span className="mode-pill">{headline}</span><button className="icon-btn" title="Refresh" onClick={refresh}>↻</button><div className="top-avatar">FP</div></div></header>
      <div className="content">
      {page==='overview'&&<>
        <SectionHead eyebrow="FINANCIAL OPERATIONS" title="Overview ✦" subtitle="A clear view of your finance workflows, in one place." action={navBtn('copilot')}/>
        <div className="stats-grid">{[['Total draft value',money(data.overview.draft_total_cents),'＄'],['Draft invoices',data.overview.draft_invoice_count||0,'▤'],['Pending approvals',data.overview.pending_count||0,'◷'],['Active customers',data.overview.customer_count||0,'♧']].map(([title,value,icon])=><div className="stat-card" key={title}><div className="stat-top"><span className="stat-label">{title}</span><span className="stat-icon">{icon}</span></div><div className="stat-value">{value}</div><div className="stat-bottom">Synthetic local records only</div></div>)}</div>
        <div className="overview-grid"><article className="panel performance"><div className="panel-heading"><div><h3>Draft volume by customer</h3><p>Approved, locally created invoice drafts</p></div><span className="subtle-chip">USD</span></div><div className="bars">
          {data.customers.map(c=>{const total=data.invoices.filter(i=>i.customer_id===c.id).reduce((n,i)=>n+i.amount_cents,0);const max=Math.max(1,...data.customers.map(x=>data.invoices.filter(i=>i.customer_id===x.id).reduce((n,i)=>n+i.amount_cents,0)));return <div className="bar-group" key={c.id}><span className="bar-label">{c.name}</span><div className="bar-track"><div className="bar-fill" style={{width:(total/max*100)+'%'}}/></div><span className="bar-amount">{money(total)}</span></div>})}
        </div></article><article className="panel attention"><div className="panel-heading"><div><h3>Needs your attention</h3><p>Items awaiting review</p></div><span className="subtle-chip">{pending.length} pending</span></div><div className="attention-list">{pending.slice(0,3).map(r=><div className="attention-item" key={r.id}><span className="attention-icon">◷</span><div><strong>{r.customer_name} · {r.external_reference}</strong><small>Human review required</small></div><span className="amount">{money(r.amount_cents)}</span></div>)}{!pending.length&&<div className="empty-small">No pending proposals.</div>}</div><button className="link-button" onClick={()=>setPage('approvals')}>Go to approval center →</button></article></div>
        <div className="panel table-panel"><div className="panel-heading"><div><h3>Recent activity</h3><p>Latest proposal and approval events</p></div></div><DataTable headers={['Event','Reference','Date']} rows={data.audit.slice(0,5).map(x=><tr key={x.id}><td>{x.action.replaceAll('_',' ')}</td><td>{x.detail}</td><td>{stamp(x.created_at)}</td></tr>)}/></div>
      </>}
      {page==='copilot'&&<><SectionHead eyebrow="INTELLIGENT WORKFLOWS" title="AI Copilot ✦" subtitle="Retrieve financial records and prepare human-approved invoice drafts." action={<span className="safety-label">⛨ Approval protected</span>}/>
        <div className="chat-layout"><div className="panel chat-main"><div className="chat-heading"><div className="assistant-icon">✦</div><div><strong>Financial assistant</strong><p>{data.health.agent_mode==='openai_langgraph'?'OpenAI + LangGraph orchestration':'Rule-based offline demo; not a live LLM'}</p></div><span className="status-indicator">● Ready</span></div><div className="chat-history">
          {!messages.length&&<div className="welcome-chat"><div className="welcome-orbit">✧</div><h2>What can I help you with?</h2><p>I can retrieve data, explain the policy, or prepare a draft proposal.</p><div className="suggestions">{['Show customers','What is the invoice approval policy?','List recent invoices'].map(x=><button className="suggestion" key={x} onClick={()=>send(x)}>{x}</button>)}</div></div>}
          {messages.map((m,i)=><React.Fragment key={i}><div className={'chat-bubble '+(m.who==='user'?'user':'bot')}><span className="bubble-label">{m.who==='user'?'YOU':'COPILOT'}</span>{m.text}</div>{m.pending&&<div className="chat-bubble bot"><strong>Approval required — Proposal #{m.pending.request_id}</strong><div className="action-row" style={{marginTop:10}}>{['approve','reject'].map(dec=><button className={'mini-button '+dec} key={dec} onClick={()=>{const r=data.requests.find(x=>x.id===m.pending.request_id);if(r)reviewFor(r,dec,m.pending.thread_id)}}>{dec==='approve'?'Approve':'Reject'}</button>)}</div></div>}</React.Fragment>)}<div ref={chatBottom}/>
        </div><form className="chat-composer" onSubmit={e=>{e.preventDefault();send()}}><textarea value={prompt} onChange={e=>setPrompt(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}} placeholder="Ask about finances or prepare an invoice…"/><div className="composer-bottom"><small>Enter to send · Shift+Enter for line break</small><button className="send-button" disabled={sending}>{sending?'Working…':'Send ↗'}</button></div></form></div>
        <aside className="chat-aside"><div className="panel aside-panel"><h3>Example workflow</h3><p>Try the sample to test the approval gates.</p><button className="example-card" onClick={()=>setPrompt('Prepare invoice for Acme Corp, $2,500, description: Consulting services, reference INV-1005.')}>Prepare invoice for Acme Corp, $2,500, description: Consulting services, reference INV-1005.<span>Use example →</span></button></div><div className="panel aside-panel"><h3>Tool execution</h3><p>Actions invoked on the latest request.</p>{trace.length?trace.map((t,i)=><div className="trace-item" key={i}><div className="trace-title"><span className="trace-icon">✓</span>{t.tool.replaceAll('_',' ')}</div><div className="trace-result">{t.result?.error||t.error||'Executed'}</div></div>):<div className="empty-small">No tools yet.</div>}</div><div className="panel aside-panel"><div className="aside-rule"><span>⛨</span><div><strong>Human approval</strong><p>Only authorized reviewers can create local invoice drafts.</p></div></div></div></aside></div>
      </>}
      {page==='invoices'&&<><SectionHead eyebrow="ACCOUNTS RECEIVABLE" title="Invoices" subtitle="Local drafts only; these have not been sent or paid." action={<button className="primary-button" onClick={()=>setModal(true)}>+ New proposal</button>}/><div className="panel table-panel"><div className="panel-heading"><div><h3>Invoice records</h3><p>Created after successful human approval</p></div><span className="subtle-chip">{data.invoices.length} records</span></div><DataTable headers={['Reference','Customer','Description','Amount','Status','Date']} rows={data.invoices.map(r=><tr key={r.id}><td className="td-strong">{r.external_reference}</td><td>{r.customer_name}</td><td>{r.description}</td><td>{money(r.amount_cents)}</td><td><Pill text={r.status}/></td><td>{stamp(r.created_at)}</td></tr>)}/></div></>}
      {page==='approvals'&&<><SectionHead eyebrow="HUMAN OVERSIGHT" title="Approval Center" subtitle="Review proposals before creating financial records." action={<span className="safety-label">⛨ Human authorization required</span>}/><div className="approval-grid"><div className="panel table-panel"><div className="panel-heading"><div><h3>Pending proposals</h3><p>Review the details before making a decision.</p></div><span className="subtle-chip">{pending.length} pending</span></div><DataTable headers={['Reference','Customer','Amount','Description','Decision']} rows={pending.map(r=><tr key={r.id}><td className="td-strong">{r.external_reference}</td><td>{r.customer_name}</td><td>{money(r.amount_cents)}</td><td>{r.description}</td><td><div className="action-row"><button className="mini-button approve" onClick={()=>reviewFor(r,'approve')}>Approve</button><button className="mini-button reject" onClick={()=>reviewFor(r,'reject')}>Reject</button></div></td></tr>)}/></div><div className="panel aside-panel"><h3>Approval controls</h3><p>Human decisions, unique references, and immutable audit events.</p><div className="control-list"><div>✓ <span>$50,000 pilot maximum</span></div><div>✓ <span>Duplicate reference protection</span></div><div>✓ <span>Idempotent approval</span></div><div>✓ <span>Decision audit trail</span></div></div><div className="notice-small">Demo approval token is not production RBAC.</div></div></div></>}
      {page==='customers'&&<><SectionHead eyebrow="DIRECTORY" title="Customers" subtitle="Synthetic organizations for finance workflow testing."/><div className="customer-grid">{data.customers.map(c=><div className="panel customer-card" key={c.id}><div className="customer-avatar">{c.name.split(' ').map(w=>w[0]).slice(0,2).join('')}</div><h3>{c.name}</h3><p>Customer ID {c.id} · Synthetic record</p></div>)}</div></>}
      {page==='audit'&&<><SectionHead eyebrow="GOVERNANCE & CONTROL" title="Audit Trail" subtitle="Time-stamped records of important state changes." action={<button className="secondary-button" onClick={refresh}>↻ Refresh log</button>}/><div className="panel table-panel"><div className="panel-heading"><div><h3>Audit events</h3><p>Most recent first</p></div></div><DataTable headers={['ID','Event','Proposal','Details','Time']} rows={data.audit.map(r=><tr key={r.id}><td>#{r.id}</td><td className="td-strong">{r.action.replaceAll('_',' ')}</td><td>#{r.entity_id}</td><td>{r.detail}</td><td>{stamp(r.created_at)}</td></tr>)}/></div></>}
      </div>
    </main>
    {notice&&<div className="toast-container"><div className="toast">{notice}</div></div>}
    {review&&<div className="modal" style={{display:'block',position:'fixed',top:'50%',left:'50%',transform:'translate(-50%,-50%)',zIndex:100}}><form onSubmit={decide}><button type="button" className="close-modal" onClick={()=>setReview(null)}>✕</button><p className="eyebrow">REVIEW PROPOSAL</p><h2>{review.decision==='approve'?'Approve':'Reject'} proposal #{review.id}</h2><div className="review-details"><strong>{review.request.customer_name}</strong> · {money(review.request.amount_cents)}<div>{review.request.external_reference}</div><div>{review.request.description}</div></div><label className="field-label">Approval token</label><input type="password" value={approvalToken} onChange={e=>setApprovalToken(e.target.value)} placeholder="APP_APPROVAL_TOKEN" required autoFocus/><p className="modal-help">Sent in X-Approval-Token; not saved in browser storage.</p><div className="modal-buttons"><button type="button" className="secondary-button" onClick={()=>setReview(null)}>Cancel</button><button className="primary-button" type="submit">Confirm decision</button></div></form></div>}
    {modal&&<div className="modal" style={{display:'block',position:'fixed',top:'50%',left:'50%',transform:'translate(-50%,-50%)',zIndex:100}}><form onSubmit={create}><button type="button" className="close-modal" onClick={()=>setModal(false)}>✕</button><p className="eyebrow">NEW PROPOSAL</p><h2>Prepare invoice</h2><p className="modal-help">Creates a pending request only.</p><label className="field-label">Customer</label><select required value={draft.customer_id||data.customers[0]?.id||''} onChange={e=>setDraft({...draft,customer_id:e.target.value})}>{data.customers.map(c=><option value={c.id} key={c.id}>{c.name}</option>)}</select><label className="field-label">Amount (USD)</label><input type="number" step="0.01" min="0.01" max="50000" required value={draft.amount} onChange={e=>setDraft({...draft,amount:e.target.value})}/><label className="field-label">Description</label><input required minLength={3} maxLength={500} value={draft.description} onChange={e=>setDraft({...draft,description:e.target.value})}/><label className="field-label">Unique reference</label><input required minLength={3} maxLength={120} pattern="[A-Za-z0-9][A-Za-z0-9._/-]*" value={draft.external_reference} onChange={e=>setDraft({...draft,external_reference:e.target.value})}/><div className="modal-buttons"><button className="secondary-button" type="button" onClick={()=>setModal(false)}>Cancel</button><button className="primary-button">Create pending proposal</button></div></form></div>}
    {(review||modal)&&<div style={{position:'fixed',inset:0,background:'#10203d85',zIndex:90}} onClick={()=>{setReview(null);setModal(false)}}/>}
  </div>
}
