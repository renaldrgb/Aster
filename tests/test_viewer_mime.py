from fastapi.testclient import TestClient
from src import store
import server

def test_pdf_viewer_modules_have_javascript_mime():
    with TestClient(server.app) as client:
        for path in ['/static/vendor/pdfjs/web/viewer.mjs','/static/vendor/pdfjs/build/pdf.mjs','/static/vendor/pdfjs/build/pdf.worker.mjs']:
            response=client.get(path)
            assert response.status_code==200
            assert response.headers['content-type'].split(';')[0]=='text/javascript'
