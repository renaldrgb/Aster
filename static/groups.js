/* Document groups change presentation only: task IDs and completion remain intact. */
function groupSchoolwork(tasks,materials){
    const groups=new Map(),byId=new Map(materials.map(m=>[m.id,m]));
    for(const t of tasks){
        const key=t.source_id;
        if(!groups.has(key))groups.set(key,{key,course:t.course,title:byId.get(key)?.title||'Classroom assignment',url:byId.get(key)?.url||t.url,tasks:[]});
        groups.get(key).tasks.push(t);
    }
    return [...groups.values()].sort((a,b)=>a.course.localeCompare(b.course)||a.title.localeCompare(b.title));
}
function courseNames(){return [...new Set([...(state.courses||[]).map(c=>c.name),...(state.tasks||[]).map(t=>t.course)])].sort();}
const expandedDocs=new Map();
function taskKind(task){return task.kind==='Homework'?'Homework':'Review';}
function schoolworkSection(group,allTasks,kind){
    const visible=group.tasks.filter(t=>taskKind(t)===kind);
    if(!visible.length)return '';
    const all=allTasks.filter(t=>taskKind(t)===kind),assignment=kind==='Homework';
    const heading=assignment?'Classroom assignments':'Study practice';
    const description=assignment?'Teacher-posted work with a due date to turn in on Classroom.':'Questions and exercises from your learning materials.';
    return `<section class="work-section ${assignment?'assignments':'review-questions'}" aria-label="${heading}">
      <div class="work-section-heading"><div><h4>${heading} <span class="section-count">${visible.length}</span></h4><p>${description}</p></div><span class="meta">${all.filter(t=>t.done).length}/${all.length} done</span></div>
      <div class="question-actions"><button class="${assignment?'':'primary'}" data-question-mode="answer" data-source-id="${esc(group.key)}" data-task-kind="${kind}">${assignment?'Help with assignments':'Answer all questions'} (${all.length}) ↗</button><button data-question-mode="research" data-source-id="${esc(group.key)}" data-task-kind="${kind}">Research all (${all.length}) ↗</button><button data-study-document="${esc(group.key)}">Go to study assistant ↗</button><small>${assignment?'Get a plan and guidance; tasks stay open until you mark them done.':'Answers open in Study Assistant.'} Includes completed items. Research sends item text to public web search.</small></div>
      <div class="question-grid">${visible.map((t,i)=>`<label class="question ${t.done?'done':''}"><input aria-label="${assignment?'Mark assignment done':'Mark question reviewed'}: ${esc(t.title)}" type="checkbox" data-task="${esc(t.id)}" ${t.done?'checked':''}><div><span class="question-number">${i+1}.${assignment?` <span class="assignment-due ${t.due&&new Date(t.due)<new Date()&&!t.done?'overdue':''}">${t.due?'Due '+date(t.due):'No due date set'}</span>`:''}</span><span class="question-text">${esc(t.title)}</span>${!assignment&&t.due?`<small>Due ${date(t.due)}</small>`:''}</div></label>`).join('')}</div>
    </section>`;
}
function documentCards(visibleTasks,compact=false){
    const allGroups=new Map(groupSchoolwork(state.tasks||[],state.materials||[]).map(g=>[g.key,g]));
    let groups=groupSchoolwork(visibleTasks,state.materials||[]);
    if(compact)groups=groups.sort((a,b)=>((a.tasks.map(t=>t.due).filter(Boolean).sort()[0])||'z').localeCompare((b.tasks.map(t=>t.due).filter(Boolean).sort()[0])||'z')).slice(0,3);
    return groups.map(g=>{
        const all=allGroups.get(g.key).tasks,done=all.filter(t=>t.done).length;
        const homework=all.filter(t=>taskKind(t)==='Homework').length,review=all.length-homework;
        const dates=[...new Set(g.tasks.filter(t=>taskKind(t)==='Homework').map(t=>t.due).filter(Boolean))];
        const due=dates.length===1?dates[0]:null;
        const overdue=due&&new Date(due)<new Date()&&g.tasks.some(t=>!t.done);
        return `<details class="document-group ${compact?'compact':''}" data-doc="${esc(g.key)}" ${!compact&&(expandedDocs.get(g.key)??true)?'open':''}>
          <summary><div class="doc-icon" aria-hidden="true">▤</div><div class="doc-name"><span class="eyebrow">${esc(g.course)}</span><h3>${esc(g.title.replace(/\.(pptx?|docx?|pdf)$/i,''))}</h3><div class="meta">${[homework?`${homework} assignment${homework===1?'':'s'}`:'',review?`${review} practice item${review===1?'':'s'}`:''].filter(Boolean).join(' · ')} · ${done} completed${dates.length?` · <span class="${overdue?'overdue':''}">${dates.length===1?'Due '+date(due):'Multiple due dates'}</span>`:''}</div></div><span class="doc-chevron">⌄</span></summary>
          <div class="doc-progress" role="progressbar" aria-label="Document completion" aria-valuenow="${done}" aria-valuemin="0" aria-valuemax="${all.length}"><span style="width:${100*done/all.length}%"></span></div>
          <div class="doc-content"><div class="doc-toolbar"><span class="muted">${g.tasks.length} ${filter==='done'&&!compact?'completed':'visible'} items</span>${g.key.startsWith('upload:')?`<button class="link" data-preview-material="${esc(g.key)}">Open document</button>`:g.url?`<button class="link" data-url="${esc(g.url)}">Open document ↗</button>`:''}</div>
          ${schoolworkSection(g,all,'Homework')}${schoolworkSection(g,all,'Review')}</div></details>`;
    }).join('');
}
document.addEventListener('toggle',e=>{if(e.target.matches?.('.document-group'))expandedDocs.set(e.target.dataset.doc,e.target.open)},true);
function applyTheme(theme){document.documentElement.dataset.theme=theme;const b=document.querySelector('#themeToggle');if(b){b.textContent=theme==='dark'?'☀ Light mode':'☾ Dark mode';b.setAttribute('aria-pressed',String(theme==='dark'));}}
document.addEventListener('click',async e=>{if(e.target.closest('#themeToggle')){const next=document.documentElement.dataset.theme==='dark'?'light':'dark';try{await api('settings','POST',{theme:next});state.theme=next;applyTheme(next);draw()}catch(err){notice(err.message)}}});

let questionActionPending=false,questionResearchId=null;
document.addEventListener('click',async e=>{
    const b=e.target.closest('[data-question-mode]');if(!b||questionActionPending)return;
    questionActionPending=true;b.disabled=true;
    try{
        const mode=b.dataset.questionMode;
        const job=await api('question-actions','POST',{mode,source_id:b.dataset.sourceId||'',kind:b.dataset.taskKind||'Review'});
        page=mode==='answer'?'study':'research';
        if(mode==='research')questionResearchId=job.id;else {activeChat=job.conversation_id;localStorage.setItem('aster-chat',activeChat)}
        notice('');await refresh();
    }catch(err){notice(err.message)}finally{questionActionPending=false;b.disabled=false}
});
function savedMessages(){return (state.messages||[]).map(m=>`<div class="message ${m.role}"><small>${m.role==='user'?'You':'Aster'}</small><div class="prose">${esc(m.body)}</div></div>`).join('');}
async function showQuestionReport(){
    if(page!=='research'||!questionResearchId||!state.reports.some(r=>r.id===questionResearchId))return;
    const r=await api('reports/'+questionResearchId);
    if(page!=='research')return;
    document.querySelector('#report').innerHTML=`<h2>${esc(r.title)}</h2><div class="prose">${esc(r.body)}</div><h3>Sources</h3>${JSON.parse(r.sources).map(s=>`<button class="link source" data-url="${esc(s.url)}">${esc(s.title||s.url)} ↗</button>`).join('')}`;
}

document.addEventListener('click',e=>{
 const button=e.target.closest('[data-study-document]');if(!button)return;
 const id=button.dataset.studyDocument,raw=(state.materials||[]).find(m=>m.id===id);
 const lesson=visibleMaterials().find(m=>m.id===id||m.attachments?.some(d=>d.id===id))||raw;
 if(!lesson){notice('This document is no longer available. Review Classroom to refresh it.');return}
 studyMaterial=lesson.id;readerClass=lesson.course;readerQuery='';readerAttachment=lesson.attachments?.some(d=>d.id===id)?id:'';
 readingView='original';localStorage.setItem('aster-reading-view',readingView);
 localStorage.setItem('aster-study-material',studyMaterial);localStorage.setItem('aster-reader-class',readerClass);
 localStorage.setItem('aster-panel:study-resources','open');localStorage.setItem('aster-panel:study-chat','open');
 page='study';draw();document.querySelector('#chat textarea')?.focus();
});
