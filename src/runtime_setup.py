"""Private, verified dependencies. Never installs a system-wide AI service."""
import atexit,hashlib,os,platform,shutil,subprocess,tarfile,threading,time,zipfile
from pathlib import Path
import requests,psutil
from src import store
LOCK=threading.Lock()
OWNED=None
FLAGS=getattr(subprocess,'CREATE_NO_WINDOW',0)
ROOT=store.DATA/'components'
OLLAMA_VERSION='v0.40.13'
ASSETS={
 'Windows':('ollama-windows-amd64.zip','7afa38624fa62ee5d8293422d0ab084c1bb4603134c7f4dafce11a033b57cc19'),
 'Darwin':('ollama-darwin.tgz','bae29252232b9e1358cf5801a7d65a07442af18fb5467cb68c7fc3711f59c511')}

def download(url,path,digest,progress=lambda *a,**k:None):
 path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix(path.suffix+'.part');sha=hashlib.sha256()
 try:
  with requests.get(url,stream=True,timeout=(20,90)) as response:
   response.raise_for_status();total=int(response.headers.get('content-length',0));done=0;last=0
   if total and shutil.disk_usage(path.parent).free<total*3:raise ValueError('Free more disk space before setup.')
   with temp.open('wb') as out:
    for chunk in response.iter_content(1024*1024):
     out.write(chunk);sha.update(chunk);done+=len(chunk)
     if time.monotonic()-last>.3:
      progress('Setting up required components: '+str(round(done/1024**2))+' MB downloaded',percent=done/total*100 if total else None);last=time.monotonic()
  if sha.hexdigest().lower()!=digest.lower():raise ValueError('Component verification failed. Retry setup.')
  temp.replace(path)
 finally:
  temp.unlink(missing_ok=True)

def extract(archive,destination):
 destination.mkdir(parents=True,exist_ok=True)
 if archive.suffix=='.zip':
  with zipfile.ZipFile(archive) as z:
   for name in z.namelist():
    if not (destination/name).resolve().is_relative_to(destination.resolve()):raise ValueError('Unsafe archive path')
   z.extractall(destination)
 else:
  with tarfile.open(archive) as t:t.extractall(destination,filter='data')

def ready():
 try:return requests.get('http://127.0.0.1:11434/api/tags',timeout=2).status_code==200
 except requests.RequestException:return False

def ensure_ai(progress=lambda *a,**k:None):
 global OWNED
 with LOCK:
  if ready():return
  system=platform.system()
  if system not in ASSETS:raise ValueError('Automatic setup supports Windows and macOS.')
  folder=ROOT/('ollama-'+OLLAMA_VERSION)
  exe=folder/('ollama.exe' if system=='Windows' else 'ollama')
  if system=='Darwin' and folder.exists() and not exe.exists():exe=next(folder.rglob('ollama'),exe)
  installed=shutil.which('ollama')
  if not exe.exists() and not installed:
   name,digest=ASSETS[system];archive=ROOT/name
   download('https://github.com/ollama/ollama/releases/download/'+OLLAMA_VERSION+'/'+name,archive,digest,progress)
   extract(archive,folder);archive.unlink(missing_ok=True)
   if system=='Darwin':
    for binary in folder.rglob('ollama*'):
     if binary.is_file():binary.chmod(binary.stat().st_mode|0o755)
    if not exe.exists():exe=next(folder.rglob('ollama'),exe)
  progress('Starting local AI engine…',percent=None)
  env=dict(os.environ,OLLAMA_HOST='127.0.0.1:11434')
  OWNED=subprocess.Popen([installed or str(exe),'serve'],env=env,creationflags=FLAGS,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(120):
   if ready():return
   if OWNED.poll() is not None:break
   time.sleep(.5)
  raise ValueError('The local AI engine could not start. Retry the download in Settings.')

def close():
 global OWNED
 if OWNED and OWNED.poll() is None:
  try:
   proc=psutil.Process(OWNED.pid);children=proc.children(recursive=True)
   for child in children:child.terminate()
   proc.terminate();psutil.wait_procs(children+[proc],timeout=5)
  except psutil.Error:pass
 OWNED=None
atexit.register(close)

def ensure_office():
 from src.document_viewer import office_executable
 existing=office_executable()
 if existing:return existing
 with LOCK:
  existing=office_executable()
  if existing:return existing
  if platform.system()=='Windows':
   archive=ROOT/'libreoffice.msi'
   download('https://download.documentfoundation.org/libreoffice/stable/26.8.2/win/x86_64/LibreOffice_26.8.2_Win_x86-64.msi',archive,'ff4b911403b67ee9e6249f820f9782c44bb32c94fdaa45b0da53a8e419e5307a')
   target=ROOT/'office'
   result=subprocess.run(['msiexec','/a',str(archive),'/qn','TARGETDIR='+str(target)],creationflags=FLAGS,timeout=600)
   if result.returncode:raise ValueError('Document component setup failed. Retry opening the document.')
   archive.unlink(missing_ok=True)
  else:
   raise ValueError('The macOS installer must include the document engine. Reinstall Aster from its macOS release.')
  exe=office_executable()
  if not exe:raise ValueError('Document engine setup is incomplete.')
  return exe
