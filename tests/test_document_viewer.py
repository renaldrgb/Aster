import io
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
import server
from src import store, library, document_viewer as viewer

@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path)
    library.init()
    data=io.BytesIO();writer=PdfWriter();writer.add_blank_page(612,792);writer.write(data)
    return data.getvalue()

def test_pdf_route_requires_auth_and_returns_original(workspace):
    saved=library.upload('Original.pdf',workspace,'Test','Lesson')
    with TestClient(server.app) as client:
        query={'material_id':saved['material_id']}
        assert client.get('/api/material-pdf',params=query).status_code==403
        response=client.get('/api/material-pdf',params=query,headers={'X-Aster-Token':server.TOKEN})
        assert response.status_code==200
        assert response.content==workspace
        assert response.headers['content-type']=='application/pdf'

def test_classroom_original_cached_by_version(workspace,monkeypatch):
    store.save_material('course:file','Test','Original.pdf','extracted text','')
    meta={'mimeType':'application/pdf','name':'Original.pdf','version':'1'}
    monkeypatch.setattr(viewer.school_reader,'document_metadata',lambda fid:dict(meta))
    download=Mock(return_value=workspace);monkeypatch.setattr(viewer.school_reader,'request',download)
    path,name=viewer.original('course:file');assert path.read_bytes()==workspace
    assert viewer.original('course:file')[0]==path
    assert download.call_count==1
    meta['version']='2'
    assert viewer.original('course:file')[0]!=path
    assert download.call_count==2

def test_chrome_receives_only_known_local_pdf(workspace,monkeypatch,tmp_path):
    saved=library.upload('Original.pdf',workspace,'Test','Lesson')
    chrome=tmp_path/'Google/Chrome/Application/chrome.exe';chrome.parent.mkdir(parents=True);chrome.touch()
    monkeypatch.setenv('PROGRAMFILES',str(tmp_path))
    launch=Mock();monkeypatch.setattr(viewer.subprocess,'Popen',launch)
    assert viewer.open_chrome(saved['material_id'])=={'ok':True}
    command=launch.call_args.args[0]
    assert command==[str(chrome),library.file_path(saved['id']).resolve().as_uri()]
    with pytest.raises(ValueError):viewer.open_chrome('../../not-a-material')
    assert launch.call_count==1

def test_classroom_powerpoint_uses_original_file_renderer(workspace,monkeypatch,tmp_path):
    store.save_material('course:slides','Test','Lesson.pptx','text without styling','')
    monkeypatch.setattr(viewer.school_reader,'document_metadata',lambda fid:{
        'mimeType':next(iter(viewer.OFFICE_MIMES)), 'name':'Lesson.pptx','version':'1'})
    monkeypatch.setattr(viewer.school_reader,'request',lambda *a,**k:b'original pptx bytes')
    monkeypatch.setattr(library,'_validate_archive',lambda *a:None)
    pdf=tmp_path/'render.pdf';pdf.write_bytes(workspace)
    def convert(path):
        assert path.suffix=='.pptx'
        assert path.read_bytes()==b'original pptx bytes'
        return pdf
    monkeypatch.setattr(viewer,'convert_office',convert)
    assert viewer.original('course:slides')==(pdf,'Lesson.pdf')

def test_native_google_slides_export_pdf(workspace,monkeypatch):
    store.save_material('course:native','Test','Lesson','plain text','')
    monkeypatch.setattr(viewer.school_reader,'document_metadata',lambda fid:{
        'mimeType':'application/vnd.google-apps.presentation','name':'Lesson','version':'2'})
    download=Mock(return_value=workspace);monkeypatch.setattr(viewer.school_reader,'request',download)
    path,name=viewer.original('course:native')
    assert path.read_bytes()==workspace
    download.assert_called_once_with('drive','files/native/export',{'mimeType':'application/pdf'},binary=True)

def test_converted_pages_are_cached(workspace,monkeypatch,tmp_path):
    source=tmp_path/'source.pptx';source.write_bytes(b'presentation')
    monkeypatch.setattr(viewer,'office_executable',lambda:tmp_path/'soffice.exe')
    def render(command,**kwargs):
        out=Path(command[command.index('--outdir')+1])/'document.pdf'
        out.write_bytes(workspace)
        return Mock(returncode=0)
    from pathlib import Path
    runner=Mock(side_effect=render);monkeypatch.setattr(viewer.subprocess,'run',runner)
    result=viewer.convert_office(source)
    assert result.read_bytes()==workspace
    assert viewer.convert_office(source)==result
    assert runner.call_count==1
