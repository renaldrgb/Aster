function renderMarkdown(text){
 const html=DOMPurify.sanitize(marked.parse(String(text||''),{breaks:true,gfm:true}),{
  ALLOWED_TAGS:['p','br','strong','em','del','h1','h2','h3','h4','h5','h6','ul','ol','li','blockquote','pre','code','hr','table','thead','tbody','tr','th','td','a'],
  ALLOWED_ATTR:['href','title','start'],ALLOW_DATA_ATTR:false
 });
 const template=document.createElement('template');template.innerHTML=html;
 template.content.querySelectorAll('a').forEach(a=>{
  const url=a.getAttribute('href')||'';
  if(/^https?:\/\//i.test(url)){a.dataset.url=url;a.removeAttribute('href');a.setAttribute('role','button');a.tabIndex=0}
  else a.removeAttribute('href');
 });
 return template.innerHTML;
}
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.matches('.markdown a[data-url]'))e.target.click()});
