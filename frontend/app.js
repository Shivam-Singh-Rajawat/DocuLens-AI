"use strict";
const $ = id => document.getElementById(id);
const state = {
  docs: [], selected: new Set(), messages: [],
  session: sessionStorage.getItem("doculens_session") || null,
  token: sessionStorage.getItem("doculens_token") || "",
  busy: false
};
const escapeHtml = s => String(s ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
function toast(message, error=false){const node=$('toast');node.textContent=message;node.classList.toggle('error',error);node.classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.classList.remove('show'),4500);}
async function api(path,{method='GET',body=null,raw=false}={}){
 const headers = {};
 if(state.token) headers['X-App-Token']=state.token;
 if(body!==null && !raw) headers['Content-Type']='application/json';
 const response=await fetch(path,{method,headers,body:body===null?undefined:raw?body:JSON.stringify(body)});
 if(!response.ok){let message=`Request failed (${response.status})`;try{let d=await response.json();message=typeof d.detail==='string'?d.detail:JSON.stringify(d.detail);}catch{}throw Error(message);}
 return response.json();
}
const fullDate = iso => {try{return new Date(iso).toLocaleDateString(undefined,{month:'short',day:'numeric'});}catch{return '';}};
async function refresh(){
 try{
  const [status,docs]=await Promise.all([api('/api/health'),api('/api/documents')]);
  const previous=state.selected;
  const priorIds=new Set(state.docs.map(d=>d.id));
  const initialized=!!$('documentList').dataset.loaded;
  state.docs=docs;
  state.selected=new Set(docs.filter(d=>!initialized||previous.has(d.id)||!priorIds.has(d.id)).map(d=>d.id));
  $('documentList').dataset.loaded='1';
  $('docCount').textContent=status.documents;
  $('chunkCount').textContent=status.chunks;
  $('libraryCount').textContent=status.documents;
  $('modelLabel').textContent=`${status.llm_provider==='gemini'&&!status.llm_ready?'Evidence only':status.llm_provider.toUpperCase()} · ${status.vector_backend}`;
  $('connection').innerHTML='<i></i> API connected';$('connection').className='connection online';
  renderDocs();renderLibrary();
 }catch(e){$('connection').innerHTML='<i></i> API unavailable';$('connection').className='connection offline';toast(e.message,true);}
}
function updateSelectionSummary(){
 $('selectionSummary').textContent=`${state.selected.size} of ${state.docs.length} sources selected`;
}
$('selectAllDocs').onclick=()=>{state.selected=new Set(state.docs.map(d=>d.id));renderDocs();};
$('clearSelectedDocs').onclick=()=>{state.selected.clear();renderDocs();};
function renderDocs(){
 updateSelectionSummary();
 const el=$('documentList');
 if(!state.docs.length){el.innerHTML='<div class="side-loading">No documents yet. Add your first source in the library.</div>';return;}
 el.innerHTML=state.docs.map(d=>`<label class="side-doc" title="${escapeHtml(d.name)}"><input type="checkbox" data-doc="${escapeHtml(d.id)}" ${state.selected.has(d.id)?'checked':''}/><span class="doc-glyph">${d.kind==='pdf'?'▧':'▤'}</span><span class="doc-name">${escapeHtml(d.name)}</span></label>`).join('');
 el.querySelectorAll('input').forEach(box=>box.addEventListener('change',e=>{e.target.checked?state.selected.add(e.target.dataset.doc):state.selected.delete(e.target.dataset.doc);updateSelectionSummary();}));
}
function renderLibrary(){
 const el=$('libraryGrid');
 if(!state.docs.length){el.innerHTML='<div class="empty-grid">Your knowledge library is empty. Upload a PDF, paste your notes, or import a public webpage to get started.</div>';return;}
 el.innerHTML=state.docs.map(d=>`<article class="library-card"><span class="kind">${escapeHtml(d.kind.toUpperCase())}</span><h3>${escapeHtml(d.name)}</h3><p>${d.pages} ${d.kind==='pdf'?'page(s)':'section'} · ${d.chunks} chunks · ${fullDate(d.created_at)}</p><div class="library-card-bottom"><button data-copy="${d.id}">Copy ID</button>${d.file_path?`<button data-open="${d.id}">Open</button>`:''}<button class="danger" data-delete="${d.id}">Delete</button></div></article>`).join('');
 el.querySelectorAll('[data-copy]').forEach(b=>b.onclick=()=>{navigator.clipboard.writeText(b.dataset.copy).then(()=>toast('Document ID copied')).catch(()=>toast(b.dataset.copy));});
 el.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>openDocument(b.dataset.open));
 el.querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>deleteDocument(b.dataset.delete));
}
async function deleteDocument(id){if(!confirm('Delete this document and all its indexed chunks?'))return;try{await api('/api/documents/'+encodeURIComponent(id),{method:'DELETE'});state.selected.delete(id);await refresh();toast('Document deleted');}catch(e){toast(e.message,true);}}
async function openDocument(id,page=null){try{const headers=state.token?{'X-App-Token':state.token}:{};const r=await fetch('/api/documents/'+encodeURIComponent(id)+'/file',{headers});if(!r.ok)throw Error('Original file is not available');const blob=await r.blob();const url=URL.createObjectURL(blob);window.open(url+(page?'#page='+encodeURIComponent(page):''),'_blank','noopener,noreferrer');setTimeout(()=>URL.revokeObjectURL(url),120000);}catch(e){toast(e.message,true);}}
function showView(view){
 document.querySelectorAll('.view').forEach(el=>el.classList.toggle('active',el.id===view+'View'));
 document.querySelectorAll('.nav-item').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
 $('viewLabel').textContent={chat:'Ask your documents',library:'Knowledge library',evaluate:'RAG evaluation'}[view];
 if(view==='library')refresh();
}
document.querySelectorAll('.nav-item').forEach(b=>b.onclick=()=>showView(b.dataset.view));
document.querySelectorAll('.upload-tab').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.upload-tab').forEach(t=>t.classList.toggle('active',t===b));
 document.querySelectorAll('.input-panel').forEach(el=>el.classList.toggle('active',el.id===b.dataset.input+'InputPanel'));
});
$('dropzone').onclick=()=> $('files').click();
$('dropzone').ondragover=e=>{e.preventDefault();$('dropzone').classList.add('over')};
$('dropzone').ondragleave=()=> $('dropzone').classList.remove('over');
$('dropzone').ondrop=e=>{e.preventDefault();$('dropzone').classList.remove('over');$('files').files=e.dataTransfer.files;updateChosen();};
$('files').onchange=updateChosen;
function updateChosen(){const selected=Array.from($('files').files);$('chosenFiles').textContent=selected.map(f=>f.name).join(' · ');$('uploadFiles').disabled=!selected.length;}
$('uploadFiles').onclick=async()=>{
 const files=Array.from($('files').files);if(!files.length)return;
 $('uploadFiles').disabled=true;let ok=0;
 for(const file of files){try{const form=new FormData();form.append('file',file);await api('/api/documents/upload',{method:'POST',body:form,raw:true});ok++;}catch(e){toast(`${file.name}: ${e.message}`,true);}}
 $('files').value='';updateChosen();await refresh();if(ok)toast(`${ok} document(s) indexed successfully`);
};
$('uploadText').onclick=async()=>{const btn=$('uploadText');btn.disabled=true;try{await api('/api/documents/text',{method:'POST',body:{title:$('textTitle').value||'Pasted notes',content:$('textContent').value}});$('textContent').value='';await refresh();toast('Text indexed successfully');}catch(e){toast(e.message,true);}finally{btn.disabled=false;}};
$('uploadUrl').onclick=async()=>{const btn=$('uploadUrl');btn.disabled=true;try{await api('/api/documents/url',{method:'POST',body:{url:$('webUrl').value}});$('webUrl').value='';await refresh();toast('Web content indexed');}catch(e){toast(e.message,true);}finally{btn.disabled=false;}};
$('refreshDocs').onclick=refresh;$('reloadLibrary').onclick=refresh;

// Chat attachments: staged locally, indexed on Send and scoped to that question.
let pendingChatFiles = [];
const supportedChatExtensions = /\.(pdf|docx|txt|md|markdown|html|htm|csv|json)$/i;
function renderChatAttachments(){
 const box=$('chatAttachments');
 box.innerHTML=pendingChatFiles.map((file,index)=>`<span class="chat-file-chip" title="${escapeHtml(file.name)}"><span aria-hidden="true">▧</span><span class="chat-file-name">${escapeHtml(file.name)}</span><button type="button" aria-label="Remove ${escapeHtml(file.name)}" data-remove-chat-file="${index}">×</button></span>`).join('');
 box.querySelectorAll('[data-remove-chat-file]').forEach(button=>button.onclick=()=>{
   if(state.busy)return;
   pendingChatFiles.splice(Number(button.dataset.removeChatFile),1);renderChatAttachments();
 });
}
function addChatFiles(files){
 let added=0;
 for(const file of Array.from(files||[])){
   if(!file || !file.size)continue;
   const name=(file.name||'').trim();
   if(!supportedChatExtensions.test(name)){toast(`Unsupported file: ${name||'unnamed file'}`,true);continue;}
   if(file.size>20*1024*1024){toast(`${name} exceeds the 20 MB upload limit`,true);continue;}
   if(pendingChatFiles.length>=10){toast('Attach up to 10 documents per message',true);break;}
   if(pendingChatFiles.some(f=>f.name===name&&f.size===file.size&&f.lastModified===file.lastModified))continue;
   pendingChatFiles.push(file);added++;
 }
 renderChatAttachments();
 if(added)note(`${added} document(s) attached. Press Send to index and ask about them.`);
 return added;
}
$('chatAttachButton').onclick=()=>{if(!state.busy)$('chatFiles').click();};
$('chatFiles').addEventListener('change',e=>{addChatFiles(e.target.files);e.target.value='';});
function chatComposerDrop(event){
 if(!event.dataTransfer?.files?.length)return;
 event.preventDefault();event.stopPropagation();
 $('chatView').classList.remove('drop-active');
 addChatFiles(event.dataTransfer.files);
}
function chatComposerPaste(event){
 const files=Array.from(event.clipboardData?.items||[])
   .filter(item=>item.kind==='file').map(item=>item.getAsFile()).filter(Boolean);
 if(!files.length)return; // Ordinary Ctrl+V text still pastes into the question.
 const normalized=files.map(file=>{
   if(supportedChatExtensions.test(file.name))return file;
   if(file.type==='application/pdf')return new File([file],'pasted-document.pdf',{type:file.type});
   return file;
 });
 if(normalized.length){event.preventDefault();addChatFiles(normalized);}
}
$('chatView').addEventListener('dragover',event=>{
 if(!Array.from(event.dataTransfer?.types||[]).includes('Files'))return;
 event.preventDefault();event.dataTransfer.dropEffect='copy';$('chatView').classList.add('drop-active');
});
$('chatView').addEventListener('dragleave',event=>{
 if(!$('chatView').contains(event.relatedTarget))$('chatView').classList.remove('drop-active');
});
$('chatView').addEventListener('drop',chatComposerDrop);
$('chatView').addEventListener('paste',chatComposerPaste);
async function uploadChatAttachments(){
 const uploadedIds=[];
 const uploadedNames=[];
 for(const file of [...pendingChatFiles]){
   note(`Indexing ${file.name}…`);
   const form=new FormData();
   form.append('file',file,file.name);
   try{
     const saved=await api('/api/documents/upload',{method:'POST',body:form,raw:true});
     uploadedIds.push(saved.id);uploadedNames.push(file.name);
     pendingChatFiles=pendingChatFiles.filter(item=>item!==file);
     renderChatAttachments();
   }catch(error){
     await refresh();
     throw Error(`Upload failed for ${file.name}: ${error.message}`);
   }
 }
 if(uploadedIds.length){
   await refresh();
   state.selected=new Set(uploadedIds);
   renderDocs();
   if($('mode').value==='chat')$('mode').value='qa';
 }
 return {uploadedIds,uploadedNames};
}
function formatText(text){return escapeHtml(text).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\[(\d+)\]/g,(all,n)=>`<button type="button" class="citation" data-citation="${n}">[${n}]</button>`);}
function appendMessage(role,text,extra=null){
 $('hero').classList.add('hidden');$('messages').classList.add('active');
 const card=document.createElement('div');card.className='message '+(role==='user'?'user':'assistant');
 const person=role==='user'?'You':'DocuLens AI';const avatar=role==='user'?'●':'✦';
 let sourceMarkup='';
 if(extra?.sources?.length){sourceMarkup=`<details class="source-summary"><summary>▤ ${extra.sources.length} retrieved evidence excerpts ${extra.reranked?'· Reranked':''}</summary><div class="source-items">${extra.sources.map(s=>`<div class="source-item" id="source-${s.number}"><b>[${s.number}] ${escapeHtml(s.source_name)}</b><small>${s.page?'Page '+s.page:'Text source'} · ${s.selection_method==='document-overview'?'Document overview':s.selection_method==='passage-match'?'Matching source passage':'Vector similarity '+s.semantic_score}</small><p>${escapeHtml(s.excerpt)}</p>${s.origin?`<button data-source-url="${escapeHtml(s.origin)}">Open webpage</button>`:s.has_file?`<button data-source-open="${escapeHtml(s.source_id)}" data-source-page="${s.page||''}">Open original</button>`:''}</div>`).join('')}</div></details>`;}
 card.innerHTML=`<div class="avatar ${role==='assistant'?'ai':''}">${avatar}</div><div class="bubble"><div class="message-head"><b>${person}</b><small>${role==='assistant'&&extra?.provider?escapeHtml(extra.provider)+' · '+extra.retrieval_ms+' ms retrieval':''}</small></div><div class="message-text">${formatText(text)}</div>${sourceMarkup}</div>`;
 $('messages').appendChild(card);$('messages').scrollTop=$('messages').scrollHeight;
 card.querySelectorAll('[data-citation]').forEach(btn=>btn.onclick=()=>{const target=card.querySelector('#source-'+btn.dataset.citation);if(target){const parent=target.closest('details');parent.open=true;target.scrollIntoView({behavior:'smooth',block:'nearest'});}});
 card.querySelectorAll('[data-source-open]').forEach(btn=>btn.onclick=()=>openDocument(btn.dataset.sourceOpen,btn.dataset.sourcePage||null));
 card.querySelectorAll('[data-source-url]').forEach(btn=>btn.onclick=()=>window.open(btn.dataset.sourceUrl,'_blank','noopener,noreferrer'));
}
function note(message){const n=$('notice');n.hidden=!message;n.textContent=message||'';}
async function sendMessage(event){
 event?.preventDefault();if(state.busy)return;
 const typedQuestion=$('question').value.trim();
 const hasAttachments=pendingChatFiles.length>0;
 const isGeneral=$('mode').value==='chat'&&!hasAttachments;
 if(!typedQuestion&&!hasAttachments)return;
 if(!hasAttachments&&!state.docs.length&&!isGeneral){note('Attach a PDF here or choose General chat for ordinary questions.');return;}
 if(!hasAttachments&&!state.selected.size&&!isGeneral){note('Select a document, attach a file, or choose General chat.');return;}
 state.busy=true;$('send').disabled=true;$('chatAttachButton').disabled=true;
 $('send').textContent=hasAttachments?'Indexing...':'Thinking...';
 try{
   const {uploadedIds,uploadedNames}=hasAttachments
     ? await uploadChatAttachments():{uploadedIds:[],uploadedNames:[]};
   const question=typedQuestion||'Summarize the attached document(s), highlighting important facts and citing the sources.';
   const sourceIds=isGeneral?[]:(uploadedIds.length?uploadedIds:Array.from(state.selected));
   if(!sourceIds.length&&!isGeneral)throw Error('Select or attach at least one document before sending.');
   note('');$('question').value='';
   appendMessage('user',question+(uploadedNames.length?'\n\n📎 '+uploadedNames.join(' · '):''));
   $('send').textContent='Thinking...';
   const payload={question,session_id:state.session,source_ids:sourceIds,mode:$('mode').value,top_k:Number($('topK').value),rerank:$('rerank').checked,custom_instructions:$('customInstructions').value};
   const result=await api('/api/chat',{method:'POST',body:payload});
   state.session=result.session_id;sessionStorage.setItem('doculens_session',state.session);
   appendMessage('assistant',result.answer,result);
   if(result.warnings?.length)toast(result.warnings.join(' '));
 }catch(e){
   if(!$('question').value)$('question').value=typedQuestion;
   note(e.message);
   toast(e.message,true);
 }finally{
   state.busy=false;$('send').disabled=false;$('chatAttachButton').disabled=false;
   $('send').innerHTML='Send <span>➜</span>';
 }
}
$('mode').addEventListener('change',()=>{
 const general=$('mode').value==='chat';
 const finding=$('mode').value==='find';
 $('question').placeholder=general?'Ask anything (no document citations)...':
    finding?'Which topic, quote, or passage should I find?':'Ask about your documents, or attach a PDF...';
 $('chatModeHint').textContent=general
  ? 'General chat uses Gemini without searching uploaded documents.'
  : finding?'Find content quotes matching PDF passages with clickable page references. No Gemini generation needed.'
  : 'Document modes use retrieved evidence with page references.';
 $('topK').disabled=general;
 $('rerank').disabled=general;
});
$('chatForm').onsubmit=sendMessage;
$('question').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();}};
$('newChat').onclick=()=>{state.session=null;sessionStorage.removeItem('doculens_session');pendingChatFiles=[];renderChatAttachments();$('messages').innerHTML='';$('messages').classList.remove('active');$('hero').classList.remove('hidden');$('question').value='';note('');showView('chat');toast('New conversation started');};
document.querySelectorAll('.suggestion').forEach(btn=>btn.onclick=()=>{$('question').value=btn.dataset.question;if(btn.dataset.mode){$('mode').value=btn.dataset.mode;$('mode').dispatchEvent(new Event('change'));}$('question').focus();});
$('runEval').onclick=async()=>{
 const output=$('evalResults');$('runEval').disabled=true;
 try{
  const cases=JSON.parse($('evalJson').value);
  if(!Array.isArray(cases))throw Error('Test set must be a JSON array.');
  const data=await api('/api/evaluate',{method:'POST',body:{cases,top_k:Number($('evalK').value)}});
  output.innerHTML=`<div class="metrics"><div class="metric-card"><strong>${(data.recall_at_k*100).toFixed(1)}%</strong><small>Recall@K</small></div><div class="metric-card"><strong>${data.mrr.toFixed(3)}</strong><small>Mean reciprocal rank</small></div><div class="metric-card"><strong>${data.mean_latency_ms} ms</strong><small>Mean retrieval latency</small></div></div>`+data.cases.map(c=>`<div class="eval-case"><b>${escapeHtml(c.question)}</b>Recall: ${c.recall_at_k} · Reciprocal rank: ${c.reciprocal_rank} · ${c.latency_ms}ms</div>`).join('');
  toast('Retrieval evaluation finished');
 }catch(e){toast(e.message,true);}finally{$('runEval').disabled=false;}
};
$('tokenButton').onclick=()=>{$('tokenInput').value=state.token;$('tokenModal').hidden=false;};
$('cancelToken').onclick=()=>{$('tokenModal').hidden=true;};
$('saveToken').onclick=()=>{state.token=$('tokenInput').value.trim();sessionStorage.setItem('doculens_token',state.token);$('tokenModal').hidden=true;refresh();};
$('tokenModal').onclick=e=>{if(e.target===$('tokenModal'))$('tokenModal').hidden=true;};
async function restoreChat(){if(!state.session)return;try{const result=await api('/api/sessions/'+encodeURIComponent(state.session));for(const m of result.messages)appendMessage(m.role,m.content);}catch{}}
(async()=>{await refresh();await restoreChat();})();
