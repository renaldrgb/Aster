// Collapsing only changes presentation; forms, viewers and chat drafts stay mounted.
function panelIsClosed(key){const saved=localStorage.getItem('aster-panel:'+key);return saved==='closed'||(saved===null&&key==='reading-controls')}
function addPanelToggle(panel,key,label,kind='card'){
 if(!panel||panel.querySelector(':scope > .panel-toggle'))return;
 panel.dataset.panelKey=key;panel.dataset.panelKind=kind;
 const button=document.createElement('button');button.type='button';button.className='panel-toggle';
 const apply=()=>{const closed=panelIsClosed(key);panel.classList.toggle('panel-folded',closed);button.textContent=closed?'▸ Expand '+label:'▾ Collapse';button.setAttribute('aria-expanded',String(!closed));button.setAttribute('aria-label',(closed?'Expand ':'Collapse ')+label);syncPanelWidths()};
 button.onclick=()=>{localStorage.setItem('aster-panel:'+key,panel.classList.contains('panel-folded')?'open':'closed');apply();window.dispatchEvent(new Event('resize'))};
 panel.prepend(button);apply();
}
function syncPanelWidths(){
 const frame=document.querySelector('#workspaceFrame'),shell=document.querySelector('.study-shell');
 if(frame){frame.classList.toggle('nav-folded',!!document.querySelector('#workspaceNav.panel-folded'));frame.classList.toggle('context-folded',!!document.querySelector('#workspaceContext.panel-folded'))}
 if(shell){shell.classList.toggle('chat-folded',!!shell.querySelector('.chat-panel.panel-folded'));shell.classList.toggle('lesson-folded',!!shell.querySelector('.study-resources.panel-folded'))}
}
function installPanelControls(){
 addPanelToggle(document.querySelector('.reader-controls'),'reading-controls','document controls','controls');
 addPanelToggle(document.querySelector('#workspaceNav'),'navigation','sidebar','sidebar');
 addPanelToggle(document.querySelector('#workspaceContext'),'context','details','sidebar');
 addPanelToggle(document.querySelector('.chat-panel'),'study-chat','chat','pane');
 addPanelToggle(document.querySelector('.study-resources'),'study-resources','lesson','pane');
 if(page!=='overview')document.querySelectorAll('#view .card').forEach((panel,index)=>{
  const title=panel.querySelector(':scope > h2,:scope > h3');
  if(title)addPanelToggle(panel,page+':'+title.textContent.trim()+':'+index,title.textContent.trim(),'card');
 });
 syncPanelWidths();
}
