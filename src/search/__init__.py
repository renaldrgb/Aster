import socket,ipaddress
from urllib.parse import urlparse,urljoin
import requests
from bs4 import BeautifulSoup

def public_url(url):
    parsed=urlparse(url)
    if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use a public HTTP(S) source.')
    addresses=socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80))
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Private network sources are not available to research.')
    return url

def fetch_webpage_content(url,timeout=15):
    for _ in range(5):
        public_url(url)
        with requests.get(url,timeout=timeout,stream=True,allow_redirects=False,headers={'User-Agent':'Aster Academic Research/1.0'}) as r:
            if r.is_redirect:
                url=urljoin(url,r.headers.get('Location',''));continue
            r.raise_for_status()
            data=bytearray()
            for part in r.iter_content(65536):
                data.extend(part)
                if len(data)>2*1024*1024:break
        soup=BeautifulSoup(bytes(data),'html.parser')
        title=soup.title.get_text(' ',strip=True) if soup.title else url
        for element in soup(['script','style','nav','footer','noscript']):element.decompose()
        return {'success':True,'title':title,'content':soup.get_text('\n',strip=True)[:60000]}
    raise ValueError('Too many redirects.')
