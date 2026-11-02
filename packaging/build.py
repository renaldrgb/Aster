import hashlib,os,platform,shutil,subprocess,sys,urllib.request,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];os.chdir(root)
def fetch(url,path,digest):
 urllib.request.urlretrieve(url,path)
 if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise RuntimeError('Download verification failed')
mac=sys.platform=='darwin'
if mac:
 from PIL import Image
 Image.open('static/aster-icon.png').save('static/aster.icns')
args=[sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--name','Aster','--icon','static/aster.icns' if mac else 'static/aster.ico','--add-data','static'+os.pathsep+'static','--add-data','LICENSE'+os.pathsep+'.','--collect-all','webview','desktop.py']
subprocess.run(args,check=True)
Path('release').mkdir(exist_ok=True)
if mac:
 arm=platform.machine()=='arm64';ver='26.8.2' if arm else '25.8.7';arch='aarch64' if arm else 'x86_64';filename=f'LibreOffice_{ver}_MacOS_'+('aarch64' if arm else 'x86-64')+'.dmg'
 digest='9f24fe83ab1ed5c95eb3df580119f32932f713e577feeac02bf619fb00749b55' if arm else '110439f207b5e420d7c8e441180c8374431761d549a1c14b584045ac56cd71c5'
 fetch(f'https://download.documentfoundation.org/libreoffice/stable/{ver}/mac/{arch}/{filename}','build/office.dmg',digest)
 mount=root/'build/office-mount';mount.mkdir(exist_ok=True)
 subprocess.run(['hdiutil','attach','build/office.dmg','-nobrowse','-mountpoint',str(mount)],check=True)
 try:shutil.copytree(mount/'LibreOffice.app','dist/Aster.app/Contents/Resources/LibreOffice.app',symlinks=True,dirs_exist_ok=True)
 finally:subprocess.run(['hdiutil','detach',str(mount)],check=True)
 subprocess.run(['codesign','--force','--deep','--sign','-','dist/Aster.app'],check=True)
 subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent','dist/Aster.app','release/Aster-macOS-'+platform.machine()+'.zip'],check=True)
else:
 urllib.request.urlretrieve('https://go.microsoft.com/fwlink/p/?LinkId=2124703','packaging/MicrosoftEdgeWebview2Setup.exe')
 subprocess.run([shutil.which('pwsh') or 'powershell','-NoProfile','-Command',"if((Get-AuthenticodeSignature 'packaging/MicrosoftEdgeWebview2Setup.exe').Status -ne 'Valid'){exit 1}"],check=True)
 compiler=shutil.which('iscc') or str(Path(os.environ['LOCALAPPDATA'])/'Programs/Inno Setup 6/ISCC.exe')
 subprocess.run([compiler,'packaging/windows.iss'],check=True)
