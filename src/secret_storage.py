import sys,hashlib
from pathlib import Path

def protect(data,path):
 if sys.platform=='win32':
  import win32crypt
  return win32crypt.CryptProtectData(data,'Aster',None,None,None,0)
 import keyring,base64
 identity=hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()
 keyring.set_password('Aster',identity,base64.b64encode(data).decode())
 return ('keychain:'+identity).encode()

def unprotect(data):
 if sys.platform=='win32':
  import win32crypt
  return win32crypt.CryptUnprotectData(data,None,None,None,0)[1]
 import keyring,base64
 value=keyring.get_password('Aster',data.decode().removeprefix('keychain:'))
 if value is None:raise ValueError('Saved credential missing from Keychain. Reconnect in Settings.')
 return base64.b64decode(value)
