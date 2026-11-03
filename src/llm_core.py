import httpx,json
from src.store import setting

async def llm_call_async(url=None,model=None,messages=None,temperature=.3,max_tokens=4096,headers=None,timeout=180,format=None,**kwargs):
    model=model or setting('model','qwen3.5-desktop:latest')
    if setting('ai_provider','local')=='openrouter':
        from src.ai_settings import cloud_key
        key=cloud_key()
        if not key:raise ValueError('Add a cloud API key in Settings.')
        cloud_payload={'model':setting('cloud_model',''),'messages':messages,'temperature':temperature,'max_tokens':max_tokens}
        if format is not None:cloud_payload['response_format']={'type':'json_object'}
        async with httpx.AsyncClient(timeout=max(timeout,180)) as client:
            response=await client.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':'Bearer '+key},json=cloud_payload)
            if response.status_code>=400:raise ValueError('Cloud AI request failed (HTTP '+str(response.status_code)+'). Check the model ID, key and account credit in Settings.')
            result=response.json()
            if result.get('error'):raise ValueError('Cloud AI returned an error. Check your model and account credit.')
            return result['choices'][0]['message']['content']
    payload={'model':model,'messages':messages,'stream':False,'think':False,
             'options':{'temperature':temperature,'num_ctx':kwargs.get('context_size',32768),'num_predict':max_tokens}}
    if format is not None:payload['format']=format
    async with httpx.AsyncClient(timeout=max(timeout,180)) as client:
        try:
            response=await client.post('http://127.0.0.1:11434/api/chat',json=payload)
        except httpx.TimeoutException as e:
            raise ValueError('Local AI timed out after '+str(max(timeout,180))+' seconds. Use a smaller model or close other apps, then retry. Saved analysis progress is kept.') from e
        except httpx.ConnectError as e:
            raise ValueError('Cannot reach the local AI engine. Check AI settings and try again.') from e
        if response.status_code>=400:
            try:detail=str(response.json().get('error',''))
            except (ValueError,AttributeError):detail=''
            if any(word in detail.lower() for word in ('memory','allocation','out of')):
                raise ValueError('The local model ran out of available memory. Select a smaller model in Settings or close other apps, then retry.')
            raise ValueError('Local AI failed (HTTP '+str(response.status_code)+'). Check that the selected model is downloaded and the engine is running.')
        return response.json()['message']['content']

def json_value(text):
    text=text.strip()
    if text.startswith('```'):text='\n'.join(text.splitlines()[1:-1])
    start=text.find('{');end=text.rfind('}')
    if start<0:raise ValueError('The model did not return structured results.')
    return json.loads(text[start:end+1])
