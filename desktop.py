"""Aster's independent Windows host. Only processes started here are stopped."""
import os,sys,socket,threading,time,subprocess,shutil,logging
from pathlib import Path
import requests,uvicorn,webview
def main():
    guard=socket.socket()
    try:guard.bind(('127.0.0.1',17069))
    except OSError:return
    from src.store import DATA
    logging.basicConfig(filename=str(DATA/'aster.log'),level=logging.WARNING)
    from src import runtime_setup
    try:
        # Start an available engine without delaying the UI or downloading anything.
        def start_existing():
            folder=runtime_setup.ROOT/('ollama-'+runtime_setup.OLLAMA_VERSION)
            if shutil.which('ollama') or folder.exists():
                try:runtime_setup.ensure_ai()
                except Exception:logging.exception('AI engine startup')
        threading.Thread(target=start_existing,daemon=True).start()
        import server
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        host=uvicorn.Server(uvicorn.Config(server.app,host='127.0.0.1',port=port,log_config=None,access_log=False))
        thread=threading.Thread(target=lambda:host.run(sockets=[sock]),daemon=True);thread.start()
        for _ in range(100):
            if host.started:break
            time.sleep(.1)
        if not host.started:raise RuntimeError('The local workspace could not start.')
        window=webview.create_window('Aster - Your study space',f'http://127.0.0.1:{port}',width=1280,height=900,min_size=(850,650),background_color='#f6f5f0')
        webview.start(gui='cocoa' if sys.platform=='darwin' else 'edgechromium',private_mode=True,icon=str(Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'static/aster.ico'))
        host.should_exit=True;thread.join(timeout=4)
    except Exception:
        logging.exception('Aster startup failed')
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,'Aster could not start. Details are in '+str(DATA/'aster.log'),'Aster',16)
    finally:
        runtime_setup.close()
        guard.close()

if __name__=='__main__':main()
