function visibleMaterials(){return (state.materials||[]).filter(m=>!m.hidden_in_library)}
async function mountDocumentPages(container,m){
  container.innerHTML='<p class="muted document-loading" role="status">Loading original pages… Presentations may take a moment on first opening.</p>';
  try{
    const response=await fetch('/api/material-pdf?material_id='+encodeURIComponent(m.id),{headers:{'X-Aster-Token':window.ASTER_TOKEN}});
    if(!response.ok){const error=await response.json();throw Error(error.detail||'Could not load original pages.')}
    const data=await response.arrayBuffer();if(!container.isConnected)return;
    const frame=document.createElement('iframe');frame.title='Original pages: '+m.title;
    frame.src='/static/vendor/pdfjs/web/viewer.html?file=#zoom=page-width&pagemode=none';
    frame.addEventListener('load',async()=>{try{
      if(!container.isConnected)return;
      const viewer=await new Promise((resolve,reject)=>{
        const started=Date.now();
        const check=()=>{
          if(!container.isConnected){reject(Error('Document view closed.'));return}
          const app=frame.contentWindow?.PDFViewerApplication;
          if(app){resolve(app);return}
          if(Date.now()-started>20000){reject(Error('The PDF viewer could not start. Please update Aster and your system web viewer, then reopen the document.'));return}
          setTimeout(check,50);
        };check();
      });
      await Promise.race([viewer.initializedPromise,new Promise((_,reject)=>setTimeout(()=>reject(Error('PDF viewer initialization timed out. Reopen the document to retry.')),30000))]);
      await viewer.open({data:new Uint8Array(data),isEvalSupported:false,disableFontFace:true});
      viewer.pdfSidebar?.close();viewer.pdfViewer.currentScaleValue='page-width';
    }catch(error){if(container.isConnected)container.textContent='Unable to render document: '+error.message}},{once:true});
    container.replaceChildren(frame);
  }catch(error){if(container.isConnected){container.innerHTML='<p class="document-loading" role="alert"></p>';container.firstChild.textContent=error.message}}
}
function supportsOriginalPages(m){
 if(m?.attachments?.length)return m.attachments.some(supportsOriginalPages);
 const f=(state.library||[]).find(x=>x.material_id===m?.id);
 return !!m&&(f?.mime==='application/pdf'||/\.(pdf|pptx|docx)$/i.test(f?.name||m.title||'')||/^https:\/\/docs\.google\.com\/(presentation|document)\//i.test(m.url||''));
}
// The library keeps originals locally; previews never send files to a web viewer.
let libraryClass='', libraryQuery='', quizClass='', quizTopic='', quizCount=5;
let currentQuiz=null, quizDrafts={}, pendingQuizJob='', quizLoading='', previewBlob='', pdfPreview=null;
function learningClasses(){return [...new Set([...(state.courses||[]).map(c=>c.name),...(state.materials||[]).map(m=>m.course)])].filter(Boolean).sort()}
function options(items,selected){return items.map(c=>`<option value="${esc(c)}" ${c===selected?'selected':''}>${esc(c)}</option>`).join('')}
function materialFiles(){const uploads=new Map((state.library||[]).map(f=>[f.material_id,f]));return visibleMaterials().map(m=>({...m,file:uploads.get(m.id)}))}
function drawLibrary(){
  view.innerHTML=heading('YOUR LIBRARY','A home for every lesson.','Save your school files, read them here, and turn them into a study session.')+`
  <form id="libraryUpload" class="card upload-panel"><div><div class="eyebrow">ADD TO YOUR SHELF</div><h2>Bring your schoolwork.</h2><p class="muted">PDF, Word, PowerPoint, text and images · up to 20 MB each.<br>Files stay saved in your Aster workspace.</p></div>
  <div class="upload-fields"><label>Schoolwork file<input type="file" name="file" required accept=".pdf,.docx,.pptx,.txt,.md,.png,.jpg,.jpeg"></label><div class="field-pair"><label>Class<input name="course" list="libraryClasses" required maxlength="200" placeholder="Select or enter a class"></label><label>Topic / tema<input name="topic" required maxlength="200" placeholder="For example: Network components"></label></div><datalist id="libraryClasses">${options(learningClasses(),'')}</datalist><button class="primary" type="submit">Upload & save</button><small class="upload-note">Use “Find tasks” after saving to add homework and review questions.</small></div></form>
  <div class="shelf-bar"><h2>Saved materials <span class="count-pill">${visibleMaterials().length}</span></h2><div class="filters"><input id="librarySearch" aria-label="Find a document" placeholder="Find a document…" value="${esc(libraryQuery)}"><select id="libraryClass" aria-label="Filter library by class"><option value="">All classes</option>${options(learningClasses(),libraryClass)}</select></div></div><div id="libraryGrid" class="library-grid"></div>`;
  drawLibraryGrid();
}
function drawLibraryGrid(){
  const items=materialFiles().filter(m=>(!libraryClass||m.course===libraryClass)&&(m.title+' '+m.course+' '+(m.search_text||m.body||'')+' '+(m.file?.name||'')).toLowerCase().includes(libraryQuery.toLowerCase()));
  document.querySelector('#libraryGrid').innerHTML=items.map(m=>`<article class="card material-card"><div class="row"><span class="file-symbol" aria-hidden="true">▤</span><small>${m.file?esc(m.file.name.split('.').pop().toUpperCase()):'CLASSROOM'}</small></div><div class="eyebrow">${esc(m.course)}</div><h3>${esc(m.title)}</h3>${m.attachments?.length?`<small>${m.attachments.length} attached document${m.attachments.length===1?'':'s'} · ${esc(m.attachments.map(d=>d.title).join(' · '))}</small>`:''}${m.file?`<small>${esc(m.file.name)} · ${(m.file.size/1024/1024).toFixed(2)} MB</small>`:''}<p class="material-excerpt muted">${esc(m.body?.slice(0,145)||'Original saved. No readable text is available for study tools.')}</p>${m.file?.warning?`<p class="file-warning">${esc(m.file.warning)}</p>`:''}<div class="material-actions"><button data-preview-material="${esc(m.id)}">Open & read</button>${m.body?.trim()?`<button class="link" data-quiz-material="${esc(m.id)}">Quiz me →</button>`:''}${m.file&&m.body?.trim()?`<button class="link" data-analyze-file="${esc(m.file.id)}">Find tasks</button>`:''}</div></article>`).join('')||empty('No materials here yet. Upload a file or review your Classroom.');
}
async function openMaterialPreview(materialId, destination){
  const m=(state.materials||[]).find(x=>x.id===materialId);if(!m)throw Error('This material is no longer available.');
  document.querySelector('#materialPreview')?.close();
  document.querySelector('#materialPreview')?.remove();
  if(previewBlob){URL.revokeObjectURL(previewBlob);previewBlob=''}
  const f=(state.library||[]).find(x=>x.material_id===materialId);
  const isPdf=supportsOriginalPages(m)&&(!m.attachments||m.attachments.length===1);
  if(isPdf&&!destination){choosePdfDestination(m);return}
  const original=isPdf||(f&&f.mime.startsWith('image/'));
  const dialog=document.createElement('dialog');dialog.id='materialPreview';dialog.className='reader-dialog';
  dialog.innerHTML=`<div class="reader-header"><div><small>${esc(m.course)}</small><h2>${esc(m.title)}</h2></div><button data-close-reader aria-label="Close document">✕</button></div><div class="reader-toolbar">${original?'<button data-reader-view="original" class="primary">Original</button>':''}<button data-reader-view="text" class="${original?'':'primary'}">Readable text</button>${m.body?.trim()?`<button data-quiz-material="${esc(m.id)}">Quiz this topic →</button>`:''}${!f&&!isPdf&&m.url?`<button class="link" data-url="${esc(m.url)}">Open in Classroom ↗</button>`:''}</div>${f?.warning?`<p class="file-warning">${esc(f.warning)}</p>`:''}<div id="originalPreview" ${original?'':'hidden'}><p class="muted">Preparing original pages… The first opening of a presentation or Word document can take a moment.</p></div><div id="textPreview" class="reader-text prose" ${original?'hidden':''}>${esc(m.body||'This file has no readable text. You can view the original, but a text version is needed for quizzes and task extraction.')}</div><small class="reader-caption">${f&&!original?'Word and PowerPoint are shown as extracted text. The original file is kept in your library.':!f?'Saved text from your last Classroom review.':'Original pages are rendered on your PC. Use Readable text for the extracted content.'}</small>`;
  if(m.attachments?.length){
    const files=document.createElement('div');files.className='reader-attachments';
    files.innerHTML='<strong>Attached documents</strong>'+m.attachments.map(d=>`<button data-preview-material="${esc(d.id)}">${esc(d.title)} ↗</button>`).join('');
    dialog.querySelector('.reader-toolbar').after(files);
  }
  document.body.append(dialog);dialog.showModal();
  dialog.addEventListener('close',()=>{pdfPreview=null;if(previewBlob){URL.revokeObjectURL(previewBlob);previewBlob=''}dialog.remove()},{once:true});
  if(original){
    try{
      if(isPdf){
        dialog.classList.add('pdf-reader-dialog');
        await mountDocumentPages(dialog.querySelector('#originalPreview'),m);
        dialog.querySelector('.reader-caption').textContent='Formatted pages · Fit to width adapts to your window. PowerPoint and Word previews use LibreOffice; fonts may vary if unavailable on this PC.';
      }else{const response=await fetch('/api/library/'+encodeURIComponent(f.id)+'/file',{headers:{'X-Aster-Token':window.ASTER_TOKEN}});if(!response.ok)throw Error('Could not load the saved original.');const blob=await response.blob();if(!dialog.isConnected)return;previewBlob=URL.createObjectURL(blob);dialog.querySelector('#originalPreview').innerHTML=`<img alt="${esc(f.name)}" src="${previewBlob}">`;}
    }catch(e){if(dialog.isConnected)dialog.querySelector('#originalPreview').textContent=e.message}
  }
}
function choosePdfDestination(m){
  const d=document.createElement('dialog');d.className='pdf-choice';
  d.innerHTML=`<div class="reader-header"><h2>Open document</h2><button aria-label="Close" data-cancel>✕</button></div><p>${esc(m.title)}</p><div class="reader-toolbar"><button class="primary" data-inside>Open in Aster</button><button data-chrome>Open in Chrome ↗</button></div><small>Both options show formatted pages with images. PowerPoint and Word files are rendered as PDF pages.</small><p role="status"></p>`;
  document.body.append(d);d.showModal();d.addEventListener('close',()=>d.remove(),{once:true});
  d.querySelector('[data-cancel]').onclick=()=>d.close();
  d.querySelector('[data-inside]').onclick=()=>{d.close();openMaterialPreview(m.id,'app').catch(e=>notice(e.message))};
  d.querySelector('[data-chrome]').onclick=async()=>{const b=d.querySelector('[data-chrome]');b.disabled=true;d.querySelector('[role="status"]').textContent='Opening original PDF…';try{await api('material-pdf/chrome','POST',{material_id:m.id});d.close()}catch(e){d.querySelector('[role="status"]').textContent=e.message;b.disabled=false}};
}
function quizMaterials(){return visibleMaterials().filter(m=>m.course===quizClass&&(m.body||'').trim().length>=40)}
function questionStem(question){
  const text=question.prompt||'', choices=question.options||[];
  // Remove only a trailing list that repeats all four selectable answers.
  // Preserve lettered examples that are part of the actual question.
  const normalize=s=>s.normalize('NFKC').toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu,'');
  const markers=[...text.matchAll(/(?:^|\s)(?:\*\*)?\(?([a-d])\s*[.)\]:](?:\*\*)?\s+/gi)];
  for(let i=0;i<=markers.length-4;i++){
    const group=markers.slice(i,i+4);if(group.map(m=>m[1].toLowerCase()).join('')!=='abcd'||choices.length!==4)continue;
    if(!group.every((m,n)=>normalize(text.slice(m.index+m[0].length,n<3?group[n+1].index:text.length))===normalize(choices[n].replace(/^\s*\(?[a-d][.)\]:]\s*/i,''))))continue;
    const stem=text.slice(0,group[0].index).trim();if(stem.length>4)return stem;
  }
  return text;
}
function drawQuizzes(){
  const classes=learningClasses();if(!classes.includes(quizClass))quizClass=classes[0]||'';
  const materials=quizMaterials();if(!materials.some(m=>m.id===quizTopic))quizTopic=materials[0]?.id||'';
  const job=(state.jobs||[]).find(j=>j.id===pendingQuizJob);
  if(job?.status==='done'){pendingQuizJob='';currentQuiz=null;loadQuiz(job.result);}
  if(job&&['error','cancelled'].includes(job.status))pendingQuizJob='';
  view.innerHTML=heading('PRACTICE, THEN PROGRESS','What have you learned?','Choose a class and topic. Aster builds a quiz from your saved lesson, then explains each answer with a source quotation.')+`
  <div class="quiz-layout"><aside><form id="quizCreate" class="card"><div class="eyebrow">YOUR NEXT QUIZ</div><label>Class<select id="quizClass" name="course" required>${options(classes,quizClass)}</select></label><label>Topic / tema<select id="quizTopic" name="material_id" required>${materials.map(m=>`<option value="${esc(m.id)}" ${m.id===quizTopic?'selected':''}>${esc(m.title)}</option>`).join('')}</select></label><label>Questions<select id="quizCount" name="count">${[3,5,10].map(n=>`<option ${n===quizCount?'selected':''}>${n}</option>`).join('')}</select></label><p class="muted">${materials.length?'Questions follow the language of your lesson.':'No readable materials in this class yet. Upload a document or review Classroom first.'}</p><button class="primary" ${!materials.length||pendingQuizJob?'disabled':''}>${pendingQuizJob?'Creating quiz…':'Create quiz →'}</button></form><div class="card quiz-history"><h3>Saved attempts</h3>${(state.quizzes||[]).filter(q=>q.course===quizClass).map(q=>`<button class="entry ${q.id===currentQuiz?.id?'selected':''}" data-open-quiz="${esc(q.id)}">${esc(q.topic)}<small>${q.submitted?q.score+' / '+q.total+' correct':'In progress'} · ${date(q.created)}</small></button>`).join('')||empty('Your quizzes and scores will stay here.')}</div></aside><div id="quizPanel">${currentQuiz?quizMarkup(currentQuiz):`<div class="card quiz-welcome"><span class="quiz-mark">?</span><h2>A little practice goes a long way.</h2><p class="muted">${pendingQuizJob?'Aster is reading your selected lesson and preparing questions.':quizLoading?'Opening your saved quiz…':'Pick your class and topic to begin. You can leave and return to any saved quiz.'}</p><p class="muted">Quizzes help you study. They don’t mark assignments complete.</p></div>`}</div></div>`;
}
function quizMarkup(q){const draft=quizDrafts[q.id]||{};return `<form id="quizAnswers" data-quiz="${esc(q.id)}" class="card quiz-paper"><div class="eyebrow">${esc(q.course)}</div><h2>${esc(q.topic)}</h2><p class="muted">${q.total} questions · ${q.submitted?'Completed '+date(q.submitted):'Choose one answer for every question.'}</p>${q.submitted?`<div class="quiz-score"><b>${q.score} / ${q.total}</b><span>${esc(q.feedback)}</span></div>`:''}${q.questions.map((question,index)=>`<fieldset class="quiz-question"><legend><span>${index+1}</span>${esc(questionStem(question))}</legend>${question.options.map((option,i)=>`<label class="quiz-option ${q.submitted&&i===question.correct?'correct':''} ${q.submitted&&i===question.selected&&!question.is_correct?'incorrect':''}"><input type="radio" name="${esc(question.id)}" value="${i}" required ${q.submitted?'disabled':''} ${(q.submitted?question.selected:draft[question.id])===i?'checked':''}><span>${esc(option)}</span>${q.submitted&&i===question.correct?'<small>Correct answer</small>':''}</label>`).join('')}${q.submitted?`<div class="quiz-explanation"><strong>${question.is_correct?'Correct':'Review this one'}</strong><p>${esc(question.explanation)}</p><blockquote>${esc(question.evidence)}</blockquote></div>`:''}</fieldset>`).join('')}${q.submitted?`<div class="row"><button type="button" data-preview-material="${esc(q.material_id)}">Review source lesson</button><small>Your result is saved.</small></div>`:'<button class="primary" type="submit">Check my answers →</button><small class="upload-note">All answers are checked together. You can review explanations afterwards.</small>'}</form>`}
async function loadQuiz(id){quizLoading=id;try{const q=await api('quizzes/'+encodeURIComponent(id));if(quizLoading!==id)return;currentQuiz=q;quizClass=q.course;quizTopic=q.material_id;quizLoading='';if(page==='quizzes')drawQuizzes();}catch(e){quizLoading='';notice(e.message)}}
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;try{
  if(b.hasAttribute('data-preview-material'))await openMaterialPreview(b.dataset.previewMaterial);
  if(b.hasAttribute('data-close-reader'))document.querySelector('#materialPreview')?.close();
  if(b.dataset.readerView){const d=b.closest('dialog'),original=b.dataset.readerView==='original';d.querySelector('#originalPreview').hidden=!original;d.querySelector('#textPreview').hidden=original;d.querySelectorAll('[data-reader-view]').forEach(x=>x.classList.toggle('primary',x===b))}
  if(b.dataset.quizMaterial){const m=(state.materials||[]).find(m=>m.id===b.dataset.quizMaterial);if(!m)throw Error('Material not found.');document.querySelector('#materialPreview')?.close();quizClass=m.course;quizTopic=m.id;currentQuiz=null;page='quizzes';draw();}
  if(b.dataset.openQuiz)await loadQuiz(b.dataset.openQuiz);
  if(b.dataset.analyzeFile){b.disabled=true;await api('library/'+b.dataset.analyzeFile+'/analyze','POST');await refresh(false)}
}catch(e){notice(e.message)}finally{if(b.dataset.analyzeFile)b.disabled=false}});
document.addEventListener('change',e=>{
  if(e.target.id==='libraryClass'){libraryClass=e.target.value;drawLibraryGrid()}
  if(e.target.id==='quizClass'){quizClass=e.target.value;quizTopic='';currentQuiz=null;drawQuizzes()}
  if(e.target.id==='quizTopic')quizTopic=e.target.value;
  if(e.target.id==='quizCount')quizCount=Number(e.target.value);
  if(e.target.closest('#quizAnswers')&&currentQuiz){const draft=quizDrafts[currentQuiz.id]||(quizDrafts[currentQuiz.id]={});draft[e.target.name]=Number(e.target.value)}
});
document.addEventListener('input',e=>{if(e.target.id==='librarySearch'){libraryQuery=e.target.value;drawLibraryGrid()}});
document.addEventListener('submit',async e=>{
  const f=e.target;if(!['libraryUpload','quizCreate','quizAnswers'].includes(f.id))return;e.preventDefault();const data=new FormData(f),button=f.querySelector('button[type="submit"],button.primary');button.disabled=true;
  try{notice('');
    if(f.id==='libraryUpload'){const file=data.get('file');if(!file.size)throw Error('Choose a nonempty schoolwork file.');if(file.size>20*1024*1024)throw Error('Files must be 20 MB or smaller.');button.textContent='Saving…';const params=new URLSearchParams({filename:file.name,course:data.get('course'),topic:data.get('topic')});const r=await fetch('/api/library/upload?'+params,{method:'POST',headers:{'X-Aster-Token':window.ASTER_TOKEN,'Content-Type':'application/octet-stream'},body:file});const result=await r.json();if(!r.ok)throw Error(result.detail||'Upload failed.');libraryClass='';libraryQuery='';await refresh();notice((result.duplicate?'This file is already saved.':'Schoolwork saved. Open it below or select Find tasks.')+(result.warning?' '+result.warning:''));}
    if(f.id==='quizCreate'){const created=await api('quizzes','POST',{course:data.get('course'),material_id:data.get('material_id'),count:Number(data.get('count'))});pendingQuizJob=created.id;currentQuiz=null;await refresh();}
    if(f.id==='quizAnswers'){const answers=Object.fromEntries([...data.entries()].map(([k,v])=>[k,Number(v)]));currentQuiz=await api('quizzes/'+encodeURIComponent(f.dataset.quiz)+'/submit','POST',{answers});delete quizDrafts[currentQuiz.id];await refresh();}
  }catch(e){notice(e.message)}finally{if(button.isConnected){button.disabled=false;if(f.id==='libraryUpload')button.textContent='Upload & save'}}
});

