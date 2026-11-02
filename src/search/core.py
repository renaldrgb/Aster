from ddgs import DDGS
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse,parse_qs,unquote
def _build_provider_chain(provider):return ['duckduckgo']
def _html_duckduckgo(query,count):
    response=requests.get('https://html.duckduckgo.com/html/',params={'q':query},timeout=20,
        headers={'User-Agent':'Mozilla/5.0 (compatible; AsterStudyResearch/1.0)'})
    response.raise_for_status();soup=BeautifulSoup(response.text,'html.parser');out=[]
    for result in soup.select('.result'):
        anchor=result.select_one('.result__a')
        if not anchor:continue
        url=anchor.get('href','')
        parsed=urlparse(url)
        if 'duckduckgo.com' in (parsed.hostname or ''):
            url=unquote(parse_qs(parsed.query).get('uddg',[url])[0])
        if urlparse(url).scheme not in {'http','https'}:continue
        snippet=result.select_one('.result__snippet')
        out.append({'url':url,'title':anchor.get_text(' ',strip=True),'content':snippet.get_text(' ',strip=True) if snippet else ''})
        if len(out)>=min(count,8):break
    return out

def _call_provider(provider,query,count):
    try:
        result=DDGS(timeout=20).text(query,max_results=min(count,8))
        return [{'url':r.get('href',''),'title':r.get('title',''),'content':r.get('body','')} for r in result]
    except Exception:
        # DDGS sometimes has a brief rate-limit or backend outage. The public
        # HTML endpoint preserves Aster's research workflow without requiring a
        # paid key or a separately hosted search service.
        fallback=_html_duckduckgo(query,count)
        if fallback:return fallback
        raise
