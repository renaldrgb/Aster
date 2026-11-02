import json
from src import school_reader as g
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import AuthorizedSession

def configure(email,client_json='',client_id='',client_secret=''):
    if '@' not in email or any(c.isspace() for c in email):raise ValueError('Enter your school email.')
    if client_json:
        try:d=json.loads(client_json)['installed']
        except Exception:raise ValueError('Choose a Google Desktop OAuth client JSON file.') from None
        if not isinstance(d,dict):raise ValueError('Choose a Google Desktop OAuth client JSON file.')
        client_id=d.get('client_id','');client_secret=d.get('client_secret','')
    if not client_id.endswith('.apps.googleusercontent.com') or not client_secret:raise ValueError('A Google client ID and secret are required.')
    g.save_secret('client',{'installed':{'client_id':client_id,'client_secret':client_secret,
        'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token','redirect_uris':['http://localhost']}})
    g.save_secret('setup',{'email':email})

def connect():
    expected=g.read_secret('setup')['email']
    flow=InstalledAppFlow.from_client_config(g.read_secret('client'),g.SCOPES,autogenerate_code_verifier=True)
    try:
        creds=flow.run_local_server(host='127.0.0.1',port=0,open_browser=True,timeout_seconds=300,
            authorization_prompt_message='',success_message='Aster received your response. Return to the app to check the connection.',
            login_hint=expected,prompt='consent',access_type='offline')
    except Warning as changed:
        if not hasattr(changed,'token'):raise ValueError('Google sign-in could not complete.') from None
        flow.oauth2session.token=changed.token;creds=flow.credentials
    granted=set(creds.granted_scopes or creds.scopes or [])
    if not g.valid_scopes(granted):raise ValueError('Grant all requested read-only permissions.')
    with AuthorizedSession(creds) as client:
        r=client.get('https://gmail.googleapis.com/gmail/v1/users/me/profile',timeout=30)
        if r.status_code!=200:raise ValueError('Check that Gmail API is enabled.')
        email=r.json().get('emailAddress','')
    if email.casefold()!=expected.casefold():raise ValueError('Select the school account entered in Settings.')
    if not creds.refresh_token:raise ValueError('Offline access was not granted. Reconnect.')
    token=json.loads(creds.to_json());token['scopes']=sorted(granted)
    g.save_secret('token',token);g.save_secret('account',{'email':email})
    return 'Connected '+email+' with read-only Google access.'

def state():
    email=''
    for key in ['account','setup']:
        if (g.STORE/(key+'.bin')).exists():email=g.read_secret(key).get('email','');break
    return {'configured':(g.STORE/'client.bin').exists(),'connected':(g.STORE/'token.bin').exists(),'email':email}
