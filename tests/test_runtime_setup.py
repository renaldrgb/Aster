import hashlib,zipfile
from unittest.mock import Mock
import pytest
from src import runtime_setup as setup

def test_reuses_existing_service(monkeypatch):
 monkeypatch.setattr(setup,'ready',lambda:True)
 launch=Mock();monkeypatch.setattr(setup.subprocess,'Popen',launch)
 setup.ensure_ai();launch.assert_not_called()

def test_rejects_archive_traversal(tmp_path):
 path=tmp_path/'bad.zip'
 with zipfile.ZipFile(path,'w') as z:z.writestr('../outside','bad')
 with pytest.raises(ValueError):setup.extract(path,tmp_path/'engine')
 assert not (tmp_path/'outside').exists()

def test_download_checks_hash_and_cleans_partial(tmp_path,monkeypatch):
 response=Mock();response.headers={'content-length':'3'};response.iter_content.return_value=[b'abc'];response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
 monkeypatch.setattr(setup.requests,'get',lambda *a,**k:response)
 path=tmp_path/'component.zip'
 with pytest.raises(ValueError,match='verification'):setup.download('https://example.test',path,'0'*64)
 assert not path.exists() and not path.with_suffix('.zip.part').exists()
 response.iter_content.return_value=[b'abc']
 setup.download('https://example.test',path,hashlib.sha256(b'abc').hexdigest())
 assert path.read_bytes()==b'abc'
