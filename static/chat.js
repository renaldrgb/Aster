let activeChat=localStorage.getItem('aster-chat')||'',chatDrafts={},chatSearch='';
function drawStudy(){
 if(activeChat&&Array.isArray(state.chats)&&!state.chats.some(c=>c.id===activeChat))activeChat='';
 const selected=(state.chats||[]).find(c=>c.id===activeChat);
 view.innerHTML=`<div class="study-shell"><aside class="chat-sidebar" aria-label="Chat history"><div class="chat-sidebar-top"><h2>Study chats</h2><button id="newChat" class="primary">＋ New chat</button><input id="chatSearch" type="search" aria-label="Search chat history" placeholder="Search chats…" value="${esc(chatSearch)}"></div><div id="chatHistory"></div></aside><section class="chat-panel" aria-label="Study assistant"><div class="chat-topbar"><div><h2>${esc(selected?.title||'Study assistant')}</h2><small>Saved in your workspace</small></div><button class="link" data-question-mode="answer">Answer all saved questions ↗</button></div><div id="messages" class="chat-messages" aria-live="polite"><div class="chat-welcome"><img src="/static/brand-star.svg" alt=""><h2>A little help with your next question.</h2><p>Explain a lesson, work through a problem, or review your schoolwork.</p></div></div><form id="chat" class="compose"><textarea name="text" required aria-label="Message Aster" placeholder="Ask about your schoolwork…" rows="2">${esc(chatDrafts[activeChat||'new']||'')}</textarea><div class="row"><small>${state.ai?.provider==='openrouter'?'Cloud AI':'Local AI'} · Enter to send · Shift+Enter for a new line</small><button class="primary" type="submit">Send ↑</button></div></form></section></div>`;
 installStudyLayout();drawChatHistory();refreshStudyMessages().catch(e=>notice(e.message));
}
function drawChatHistory(){
 const box=document.querySelector('#chatHistory');if(!box)return;
 box.innerHTML=(state.chats||[]).filter(c=>c.title.toLowerCase().includes(chatSearch.toLowerCase())).map(c=>`<button class="chat-history-item ${c.id===activeChat?'selected':''}" data-chat-id="${esc(c.id)}" ${c.id===activeChat?'aria-current="true"':''}><span>${esc(c.title)}</span><small>${date(c.updated)}</small></button>`).join('')||'<p class="muted chat-history-empty">No conversations yet.</p>';
}
async function refreshStudyMessages(){
 drawChatHistory();if(!activeChat)return;
 const cid=activeChat,box=document.querySelector('#messages');if(!box)return;
 const result=await api('chats/'+encodeURIComponent(cid));
 if(activeChat!==cid||page!=='study'||!box.isConnected)return;
 const signature=result.messages.map(m=>m.id).join(',');if(box.dataset.signature===signature)return;
 const bottom=!box.dataset.signature||box.scrollHeight-box.scrollTop-box.clientHeight<80;
 box.dataset.signature=signature;
 if(result.messages.length)box.innerHTML=result.messages.map(m=>`<article class="message ${m.role==='user'?'user':'assistant'}"><small>${m.role==='user'?'You':'Aster'}</small><div class="prose ${m.role==='user'?'':'markdown'}">${m.role==='user'?esc(m.body):renderMarkdown(m.body)}</div></article>`).join('');
 if(bottom)box.scrollTop=box.scrollHeight;
}
document.addEventListener('click',e=>{
 const item=e.target.closest('[data-chat-id]');if(!item&&!e.target.closest('#newChat,[data-new-chat]'))return;
 page='study';activeChat=item?.dataset.chatId||'';localStorage.setItem('aster-chat',activeChat);draw();
});
document.addEventListener('input',e=>{
 if(e.target.id==='chatSearch'){chatSearch=e.target.value;drawChatHistory()}
 if(e.target.matches('#chat textarea'))chatDrafts[activeChat||'new']=e.target.value;
});
document.addEventListener('keydown',e=>{
 if(e.target.matches('#chat textarea')&&e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();e.target.form.requestSubmit()}
});
