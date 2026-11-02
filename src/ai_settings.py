"""Local model downloads and an explicitly selected cloud provider."""
import json,subprocess,shutil,psutil,httpx,time
from src import store

CATALOG=[{'name':'qwen3.5:2b','gb':3.1,'ram':8,'vram':4},
         {'name':'qwen3.5:4b','gb':4.0,'ram':16,'vram':6},
         {'name':'qwen3.5:9b','gb':7.6,'ram':24,'vram':12}]

def hardware():
    ram=round(psutil.virtual_memory().total/1024**3,1);gpu='Not detected';vram=0
    try:
        result=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        name,memory=result.stdout.strip().splitlines()[0].rsplit(',',1);gpu=name.strip();vram=round(float(memory)/1024,1)
    except (OSError,ValueError,IndexError,subprocess.TimeoutExpired):pass
    suitable=[m for m in CATALOG if ram+.5>=m['ram'] and (vram>=m['vram'] if vram else m['gb']<=ram*.25)]
    recommended=suitable[-1]['name'] if suitable else None
    return {'ram_gb':ram,'gpu':gpu,'vram_gb':vram,'free_gb':round(shutil.disk_usage(store.DATA).free/1024**3,1),
        'models':[{**m,'recommended':m['name']==recommended} for m in CATALOG],
        'note':'Estimated fit, with room for context. CPU-only models can be slow; GPU detection currently supports NVIDIA.'}

def key_path():return store.DATA/'cloud-key.bin'
def cloud_key():
    if not key_path().exists():return ''
    from src import secret_storage
    return secret_storage.unprotect(key_path().read_bytes()).decode()

def status():return {'provider':store.setting('ai_provider','local'),'cloud_model':store.setting('cloud_model',''),'has_key':key_path().exists()}

def configure(provider,model,key=''):
    if provider not in ('local','openrouter'):raise ValueError('Choose Local or OpenRouter.')
    if provider=='openrouter' and (not model.strip() or not (key.strip() or key_path().exists())):raise ValueError('Enter a cloud model ID and API key.')
    if key.strip():
        from src import secret_storage
        encrypted=secret_storage.protect(key.strip().encode(),key_path())
        temporary=key_path().with_suffix('.tmp');temporary.write_bytes(encrypted);temporary.replace(key_path())
    if model.strip():store.set_setting('cloud_model',model.strip())
    store.set_setting('ai_provider',provider)

async def pull(name,progress):
    if name not in {m['name'] for m in CATALOG}:raise ValueError('Select a model from the download list.')
    model=next(m for m in CATALOG if m['name']==name)
    if shutil.disk_usage(store.DATA).free<model['gb']*1.3*1024**3:raise ValueError('Free more disk space before downloading this model.')
    import asyncio
    from src.runtime_setup import ensure_ai
    await asyncio.to_thread(ensure_ai,progress)
    layers={};started=time.monotonic();initial=None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90,connect=10)) as client:
            async with client.stream('POST','http://127.0.0.1:11434/api/pull',json={'model':name,'stream':True}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:continue
                    event=json.loads(line)
                    if event.get('error'):raise ValueError('Ollama download failed: '+event['error'])
                    if event.get('digest') and event.get('total'):
                        layers[event['digest']]=(event.get('completed',0),event['total'])
                        completed=sum(x[0] for x in layers.values());total=sum(x[1] for x in layers.values())
                        if initial is None:initial=completed
                        speed=(completed-initial)/max(time.monotonic()-started,.1)
                        progress(event.get('status','Downloading'),percent=min(99,completed/total*100),eta_seconds=(total-completed)/speed if speed>0 else None)
                    else:progress(event.get('status','Preparing download'),percent=None)
                    if event.get('status')=='success':
                        store.set_setting('model',name);store.set_setting('ai_provider','local')
                        return 'Downloaded and activated '+name+'. Local AI is ready.'
    except httpx.HTTPError:raise ValueError('Ollama could not download the model. Check Ollama and your internet connection; retry to resume.') from None
    raise ValueError('Download ended before completion. Retry to resume.')
