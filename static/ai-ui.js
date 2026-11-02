const originalDraw=draw;
draw=function(){originalDraw();if(page==='settings'){drawLayoutSettings();drawAISettings()}applyWorkspaceLayout();installPanelControls()};
function duration(seconds){seconds=Math.max(0,Math.round(seconds));return seconds<60?seconds+'s':Math.floor(seconds/60)+'m '+seconds%60+'s'}
let progressFrame=0, progressJob=null, progressReceived=0, visualProgress=0, progressLastFrame=0;
showJobs=function(jobs){
 const j=jobs.find(j=>j.status==='running'),box=document.querySelector('#job');box.hidden=!j;
 if(!j){cancelAnimationFrame(progressFrame);progressFrame=0;progressJob=null;box.dataset.jobId='';if(timer){clearInterval(timer);timer=null}return}
 if(box.dataset.jobId!==j.id){
  visualProgress=0;box.dataset.jobId=j.id;
  box.innerHTML=`${j.kind==='Google connection'?'':'<button data-action="stop">Stop</button>'}<b></b><div class="job-status"></div><div class="smooth-progress" role="progressbar" aria-label="Task progress" aria-valuemin="0" aria-valuemax="100"><div></div></div><small></small>`;
 }
 progressJob=j;progressReceived=Date.now()/1000;
 box.querySelector('b').textContent=j.kind;box.querySelector('.job-status').textContent=j.progress;
 if(!progressFrame){progressLastFrame=performance.now();progressFrame=requestAnimationFrame(animateJobProgress)}
 if(!timer)timer=setInterval(poll,1500);
};
function animateJobProgress(now){
 const j=progressJob,box=document.querySelector('#job');if(!j||box.hidden){progressFrame=0;return}
 const elapsed=Math.max(0,Date.now()/1000-j.started_at),known=typeof j.percent==='number';
 const remaining=j.eta_seconds!=null?j.eta_seconds-(Date.now()/1000-progressReceived):(j.estimate_seconds?j.estimate_seconds-elapsed:null);
 const estimated=!known&&j.estimate_seconds>0;
 const target=known?Math.max(0,Math.min(100,j.percent)):estimated?Math.min(95,elapsed/j.estimate_seconds*100):0;
 const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
 visualProgress=reduce?target:visualProgress+(target-visualProgress)*(1-Math.exp(-Math.min(now-progressLastFrame,100)/220));progressLastFrame=now;
 const bar=box.querySelector('.smooth-progress');bar.classList.toggle('indeterminate',!known&&!estimated);
 bar.firstElementChild.style.transform='scaleX('+visualProgress/100+')';
 if(known)bar.setAttribute('aria-valuenow',String(Math.round(j.percent)));else bar.removeAttribute('aria-valuenow');
 const label=`${duration(elapsed)} elapsed${known?' · '+Math.round(j.percent)+'% downloaded':''} · ${remaining===null?'Estimating time — no previous run yet':remaining>0?'About '+duration(remaining)+' remaining (estimate)':'Taking longer than expected'}${!known?' · AI completion time varies':''}`;
 const text=box.querySelector('small');if(text.textContent!==label)text.textContent=label;
 progressFrame=requestAnimationFrame(animateJobProgress);
}
function drawAISettings(){
 const a=state.ai||{};const section=document.createElement('div');section.id='aiSettings';section.className='card';section.innerHTML=`<div class="eyebrow">AI OPTIONS</div><h2>Choose where Aster thinks.</h2><form id="aiProvider"><label for="provider">AI provider</label><select id="provider" name="provider"><option value="local">Local · Ollama</option><option value="openrouter">Cloud · OpenRouter</option></select><div id="cloudFields"><p class="muted">Cloud mode sends prompts, relevant school document text and conversation context to OpenRouter and the selected model provider. Provider charges may apply. Local mode keeps AI processing on this PC.</p><label>Cloud model ID<input name="cloud_model" value="${esc(a.cloud_model)}" placeholder="Provider/model ID from OpenRouter"></label><label>OpenRouter API key<input name="key" type="password" autocomplete="off" placeholder="${a.has_key?'Saved securely — leave blank to keep':'Enter your API key'}"></label><small>Your key is encrypted for this Windows account.</small></div><p><button class="primary">Save AI provider</button> <button type="button" id="testAI">Test selected AI</button></p></form><hr><h2>Download a local model</h2><div id="hardwareInfo" class="muted">Checking RAM and graphics memory…</div><div id="modelDownloads"></div><p class="muted">Aster sets up the local AI engine automatically, then downloads and activates your model. The first setup needs internet and extra disk space. Sizes are approximate.</p>`;
 view.append(section);section.querySelector('#provider').value=a.provider||'local';toggleCloudFields();
 api('ai/hardware').then(h=>{if(page!=='settings')return;document.querySelector('#hardwareInfo').textContent=`${h.ram_gb} GB RAM · ${h.gpu}${h.vram_gb?' · '+h.vram_gb+' GB VRAM':''} · ${h.free_gb} GB free on workspace drive. ${h.note}`;document.querySelector('#modelDownloads').innerHTML=h.models.map(m=>`<div class="row model-download"><div><strong>${esc(m.name)}</strong>${m.recommended?' <span class="tag">Recommended</span>':''}<small>About ${m.gb} GB · suggested RAM ${m.ram} GB</small></div><button data-pull="${esc(m.name)}">Download</button></div>`).join('')}).catch(e=>notice(e.message));
}
function toggleCloudFields(){document.querySelector('#cloudFields').hidden=document.querySelector('#provider').value!=='openrouter'}
document.addEventListener('change',e=>{if(e.target.id==='provider')toggleCloudFields()});
document.addEventListener('submit',async e=>{if(e.target.id!=='aiProvider')return;e.preventDefault();const f=e.target,d=new FormData(f),b=f.querySelector('button');b.disabled=true;try{await api('ai/settings','POST',{provider:d.get('provider'),cloud_model:d.get('cloud_model'),key:d.get('key')});await refresh();notice('AI settings saved. Future AI tasks will use the selected provider.')}catch(e){notice(e.message)}finally{b.disabled=false}});
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;try{if(b.dataset.pull){b.disabled=true;await api('ai/download','POST',{name:b.dataset.pull});await refresh(false)}if(b.id==='testAI'){await api('ai/test','POST');await refresh(false)}}catch(e){notice(e.message)}finally{if(b.dataset.pull)b.disabled=false}});
