let readingView=localStorage.getItem('aster-reading-view')||'original';
let readerClass=localStorage.getItem('aster-reader-class')||'',readerQuery='',readerAttachment='';
let studyMaterial=localStorage.getItem('aster-study-material')||'';
function applyLayout(){state.layout='reading-room';document.documentElement.dataset.layout='reading-room'}
function studyMaterials(){return visibleMaterials().filter(m=>(m.body?.trim()||m.attachments?.length)&&(!readerClass||m.course===readerClass)&&[m.title,m.course,m.search_text||m.body||''].join(' ').toLocaleLowerCase().includes(readerQuery.toLocaleLowerCase()))}
function currentStudyMaterial(){const materials=studyMaterials();return materials.find(m=>m.id===studyMaterial||m.attachments?.some(d=>d.id===studyMaterial))||materials[0]}
function updateReaderSelection(){
 const select=document.querySelector('#studyMaterial');if(!select)return;
 const previous=studyMaterial,materials=studyMaterials(),chosen=currentStudyMaterial();studyMaterial=chosen?.id||'';
 select.innerHTML=materials.length?materials.map(m=>`<option value="${esc(m.id)}" ${m.id===studyMaterial?'selected':''}>${esc(m.title)}</option>`).join(''):'<option value="">No matching documents</option>';
 if(studyMaterial)localStorage.setItem('aster-study-material',studyMaterial);
 if(previous!==studyMaterial||!chosen){readerAttachment='';drawStudyReader()}
}
function studyTasksMarkup(){const tasks=(state.tasks||[]).filter(t=>!t.done&&t.kind==='Homework'&&t.due).sort((a,b)=>(a.due||'z').localeCompare(b.due||'z')).slice(0,3);return `<div class="study-task-card"><div class="row"><h3>Classroom assignments</h3><button class="link" data-page="work">View all ↗</button></div>${tasks.map(t=>`<button class="study-task-link" data-page="work"><strong>${esc(t.title)}</strong><small>${esc(t.course)} · ${date(t.due)}</small></button>`).join('')||'<p class="muted">No pending Classroom assignments with a due date.</p>'}</div>`}
function installStudyLayout(){
 const shell=document.querySelector('.study-shell');if(!shell)return;
 const material=currentStudyMaterial();if(material)studyMaterial=material.id;
 const panel=document.createElement('aside');panel.className='study-resources';panel.setAttribute('aria-label','Lesson and schoolwork');
 panel.innerHTML=`<div class="study-reader"><div class="reader-controls"><div class="row"><h3>${state.layout==='reading-room'?'Reading room':'Your lesson'}</h3><button class="link" data-page="library">Library ↗</button></div><label for="readerClass">Class</label><select id="readerClass"><option value="">All classes</option>${options(learningClasses(),readerClass)}</select><label for="readerSearch">Search documents</label><input id="readerSearch" type="search" placeholder="Search titles, attachments or text…" value="${esc(readerQuery)}"><label for="studyMaterial">Document / lesson</label><select id="studyMaterial"><option value="">${material?'Choose a document':'No saved documents yet'}</option>${studyMaterials().map(m=>`<option value="${esc(m.id)}" ${m.id===material?.id?'selected':''}>${esc(m.course+' · '+m.title)}</option>`).join('')}</select></div><div id="studyReadingBody"></div></div>${studyTasksMarkup()}`;
 if(document.documentElement.dataset.layout==='reading-room')shell.insertBefore(panel,shell.querySelector('.chat-panel'));else shell.append(panel);
 drawStudyReader();
}
function drawStudyReader(){
 const body=document.querySelector('#studyReadingBody');if(!body)return;
 const m=currentStudyMaterial(),reading=state.layout==='reading-room';
 const controls=body.closest('.study-reader').querySelector('.reader-controls');
 controls.querySelector('.reading-view-switch')?.remove();controls.querySelector('.reader-attachment-picker')?.remove();
 const files=m?.attachments||[],shown=files.find(d=>d.id===readerAttachment)||files[0]||m;
 if(files.length){
  readerAttachment=shown.id;
  const picker=document.createElement('label');picker.className='reader-attachment-picker';picker.innerHTML=`Attached document<select id="readerAttachment">${files.map(d=>`<option value="${esc(d.id)}" ${d.id===shown.id?'selected':''}>${esc(d.title)}</option>`).join('')}</select>`;controls.append(picker);
 }
 body.innerHTML=m?`<div class="reading-page">${reading?'':`<div class="lesson-cover"><small>${esc(m.course)}</small><h2>${esc(m.title)}</h2><span>YOUR SAVED LESSON</span></div>`}<div class="lesson-copy"><div class="eyebrow">${esc(m.course)}</div>${reading?`<h2>${esc(m.title)}</h2>`:''}<div class="prose">${esc(m.body)}</div></div></div><div class="reading-actions"><button data-preview-material="${esc(m.id)}">Open & read ↗</button><button class="link" id="askLesson">Discuss lesson</button></div>`:`<div class="empty">No documents match this class or search.<p><button data-page="library">Add schoolwork</button></p></div>`;
 if(reading&&m){
  const original=supportsOriginalPages(shown),selected=original?readingView:'text';
  const controls=body.closest('.study-reader').querySelector('.reader-controls');
  controls.querySelector('.reading-view-switch')?.remove();
  const toggle=document.createElement('div');toggle.className='reading-view-switch';toggle.setAttribute('aria-label','Document display');
  toggle.innerHTML=`<button data-reading-view="text" aria-pressed="${selected==='text'}" class="${selected==='text'?'primary':''}">Readable text</button><button data-reading-view="original" aria-pressed="${selected==='original'}" class="${selected==='original'?'primary':''}" ${original?'':'disabled title="Original pages are available for PDF, PowerPoint and Word files"'}>Original pages</button>`;
  controls.append(toggle);
  if(selected==='original'){
   body.innerHTML=`<div class="inline-document-pages"></div><div class="reading-actions"><button data-preview-material="${esc(m.id)}">Expand ↗</button><button class="link" id="askLesson">Discuss lesson</button></div>`;
   mountDocumentPages(body.querySelector('.inline-document-pages'),shown);
  }
 }
 const panel=body.closest('.study-resources');panel?.querySelector('.lesson-sources')?.remove();
 if(!reading&&panel){const sources=document.createElement('section');sources.className='lesson-sources';sources.innerHTML=`<h3>Sources</h3>${studyMaterials().slice(0,3).map((x,i)=>`<button data-preview-material="${esc(x.id)}"><b>${i+1}</b><div><strong>${esc(x.title)}</strong><small>${esc(x.course)} · Saved material</small></div></button>`).join('')||'<p class="muted">Your saved documents appear here.</p>'}`;panel.append(sources)}
 if(typeof installPanelControls==='function')installPanelControls();
}

document.addEventListener('change',e=>{if(e.target.id==='readerClass'){readerClass=e.target.value;localStorage.setItem('aster-reader-class',readerClass);updateReaderSelection()}if(e.target.id==='readerAttachment'){readerAttachment=e.target.value;drawStudyReader()}if(e.target.id==='studyMaterial'&&e.target.value){readerAttachment='';studyMaterial=e.target.value;localStorage.setItem('aster-study-material',studyMaterial);drawStudyReader()}});
document.addEventListener('click',async e=>{
 const mode=e.target.closest('[data-reading-view]');if(mode){readingView=mode.dataset.readingView;localStorage.setItem('aster-reading-view',readingView);drawStudyReader();return}
 if(e.target.closest('#askLesson')){const m=currentStudyMaterial(),input=document.querySelector('#chat textarea');if(m&&input){input.value='Explain the key ideas in "'+m.title+'" ('+m.course+').';chatDrafts[activeChat||'new']=input.value;input.focus()}}
});
// Keep the selected design's navigation and panel structure across every page.
let workspaceSearch="";
const workspacePages=[['overview','Overview'],['work','Schoolwork'],['library','Library'],['study','Study assistant'],['research','Research'],['quizzes','Quizzes'],['settings','Settings']];
function applyWorkspaceLayout(){
 document.body.dataset.workspacePage=page;
 let frame=document.querySelector('#workspaceFrame');
 if(!frame){frame=document.createElement('div');frame.id='workspaceFrame';document.querySelector('header').after(frame);const left=document.createElement('aside');left.id='workspaceNav';left.setAttribute('aria-label','Workspace sidebar');frame.append(left,document.querySelector('main'));const right=document.createElement('aside');right.id='workspaceContext';right.setAttribute('aria-label','Workspace context');frame.append(right)}
 const layout=document.documentElement.dataset.layout;
 document.querySelector('#workspaceNav').innerHTML=`<button class="workspace-brand" data-page="overview"><img src="/static/brand-star.svg" alt="">aster</button><nav class="workspace-links" aria-label="Workspace sections">${workspacePages.map(([id,name])=>`<button data-page="${id}" class="${page===id?'active':''}">${name}</button>`).join('')}</nav><div class="workspace-chat-heading"><h3>Study chats</h3><button data-new-chat class="primary">＋ New chat</button><input id="workspaceChatSearch" type="search" aria-label="Search chats" placeholder="Search chats…" value="${esc(workspaceSearch)}"></div><div class="workspace-history">${(state.chats||[]).map(c=>`<button ${c.title.toLowerCase().includes(workspaceSearch.toLowerCase())?'':'hidden'} data-chat-id="${esc(c.id)}" class="${c.id===activeChat&&page==='study'?'selected':''}"><span>${esc(c.title)}</span><small>${date(c.updated)}</small></button>`).join('')||'<p class="muted">Your conversations appear here.</p>'}</div><div class="workspace-sidebar-bottom"><button data-workspace-theme>${state.theme==='dark'?'☀ Light mode':'☾ Dark mode'}</button><small>Saved locally in Aster</small></div>`;
 const context=document.querySelector('#workspaceContext');
 context.innerHTML=layout==='reading-room'?`<div class="context-reading"><div class="eyebrow">READING SHELF</div><h2>Your class materials</h2>${visibleMaterials().slice(0,6).map(m=>`<button class="context-lesson" data-preview-material="${esc(m.id)}"><small>${esc(m.course)}</small><strong>${esc(m.title)}</strong><span>Open & read ↗</span></button>`).join('')||'<p class="muted">Save a lesson in Library to begin.</p>'}</div>${studyTasksMarkup()}`:`${studyTasksMarkup()}<div class="workspace-context-card"><div class="eyebrow">YOUR CLASSES</div>${learningClasses().map(name=>`<button data-workspace-course="${esc(name)}">${esc(name)}<span>↗</span></button>`).join('')||'<p class="muted">Connect Classroom in Settings.</p>'}</div><div class="workspace-context-card"><div class="eyebrow">CLASSROOM REVIEW</div><p>Last successful scan</p><strong>${state.last_sync?esc(new Date(state.last_sync).toLocaleString()):'Not scanned yet'}</strong><button data-action="sync">Check for new work ↗</button></div>`;
 if(page==='overview')drawWorkspaceOverview();decorateNavigation();
}
function drawWorkspaceOverview(){
 const all=state.tasks||[],assignments=all.filter(t=>t.kind==='Homework'&&t.due),pending=assignments.filter(t=>!t.done),practice=all.filter(t=>t.kind!=='Homework');
 view.innerHTML=`<div class="workspace-page-heading"><div class="eyebrow">YOUR STUDY SPACE</div><h1>A clear view of your schoolwork.</h1><p class="muted">Assignments to turn in, materials to read, and room to practise.</p></div><div class="workspace-metrics"><article><small>Assignments to turn in</small><b>${pending.length}</b><button class="link" data-page="work">View schoolwork ↗</button></article><article><small>Study practice</small><b>${practice.filter(t=>!t.done).length}</b><button class="link" data-page="work">Review questions & exercises ↗</button></article><article><small>Your classes</small><b>${learningClasses().length}</b><button class="link" data-page="library">Browse materials ↗</button></article></div><div class="workspace-overview-grid"><section class="card"><div class="row"><h2>Assignments</h2><span class="tag">From Classroom</span></div><p class="muted">Teacher-posted work with a due date. Document exercises are kept in study practice.</p>${pending.slice(0,5).map(t=>task(t)).join('')||'<div class="empty">No pending assignments with a due date.</div>'}<button data-action="sync">Review Classroom ↗</button></section><section class="card"><div class="eyebrow">CONTINUE LEARNING</div><h2>Your next study session</h2><div class="workspace-shortcuts"><button data-page="study"><strong>Study assistant</strong><small>Ask a question or continue a conversation.</small></button><button data-page="quizzes"><strong>Practise with a quiz</strong><small>Test yourself on a saved lesson.</small></button><button data-page="research"><strong>Research a topic</strong><small>Explore ideas with supporting sources.</small></button></div></section></div><section class="card"><h2>Recent activity</h2>${(state.activity||[]).slice(0,3).map(a=>`<div class="activity">${esc(a.body)}<small>${date(a.created)}</small></div>`).join('')||'<p class="muted">Your saved progress will appear here.</p>'}</section>`;
}
document.addEventListener('click',e=>{
 if(e.target.closest('[data-workspace-theme]'))document.querySelector('#themeToggle').click();
 const c=e.target.closest('[data-workspace-course]');if(c){course=c.dataset.workspaceCourse;page='work';draw()}
});

document.addEventListener('input',e=>{if(e.target.id==='workspaceChatSearch'){workspaceSearch=e.target.value;document.querySelectorAll('.workspace-history [data-chat-id]').forEach(b=>{b.hidden=!b.textContent.toLowerCase().includes(workspaceSearch.toLowerCase())})}});

function decorateNavigation(){
 const icons={overview:'M3 10.5 12 3l9 7.5 M5 9v12h14V9 M9 21v-7h6v7',work:'M8 4H4v17h16V4h-4 M8 3h8v4H8z M8 12h8 M8 16h5',library:'M3 4h7l2 2 2-2h7v16h-7l-2 2-2-2H3z M12 6v16',study:'M4 4h16v13H9l-5 4z',research:'M16 16l5 5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',quizzes:'M8 4H4v17h16V4h-4 M8 3h8v4H8z M8 13l3 3 5-6',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M10 2h4l1 4 4 1 3 4-3 3-1 5-4 1-4-1-1-4-3-3 1-4 4-1z'};
 document.querySelectorAll('header nav [data-page],.workspace-links [data-page]').forEach(b=>{if(!b.querySelector('svg'))b.insertAdjacentHTML('afterbegin',`<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${icons[b.dataset.page]||icons.study}"/></svg>`)});
}

document.addEventListener('input',e=>{if(e.target.id==='readerSearch'){readerQuery=e.target.value;updateReaderSelection()}});
