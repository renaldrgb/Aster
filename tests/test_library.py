import io
import json
import sqlite3
import zipfile

import pytest
from PIL import Image
from pypdf import PdfWriter

from src import library, store


@pytest.fixture(autouse=True)
def isolated_library(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DATA', tmp_path)
    library.init()


def office_file(suffix, content):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        if suffix == '.docx':
            archive.writestr('word/document.xml', content)
        else:
            archive.writestr('ppt/presentation.xml', '<presentation/>')
            archive.writestr('ppt/slides/slide1.xml', content)
    return output.getvalue()


def test_original_and_study_text_persist_without_exposing_disk_paths():
    data = 'Pyetje për kontroll\nÇfarë është rrjeti?'.encode()
    result = library.upload('../../lesson.txt', data, 'Networks', 'Tema 1')
    assert result['name'] == 'lesson.txt' and not result['duplicate']
    assert result['text'] == data.decode() and result['topic'] == 'Tema 1'
    assert library.file_path(result['id']).read_bytes() == data
    assert library.file_path(result['id']).name == result['id'] + '.txt'
    material = store.rows('materials')[0]
    assert material['id'] == result['material_id']
    assert material['body'] == result['text'] and material['title'] == 'Tema 1'
    library.init()
    assert library.list_files()[0] == library.get(result['id'])
    assert str(store.DATA) not in json.dumps(library.list_files())


def test_duplicates_are_per_class_topic_and_restore_missing_original():
    first = library.upload('lesson.txt', b'Example question?', 'Networks', 'Tema 1')
    library.file_path(first['id']).unlink()
    duplicate = library.upload('renamed.txt', b'Example question?', ' networks ', 'TEMA 1')
    assert duplicate['duplicate'] and duplicate['id'] == first['id']
    assert library.file_path(first['id']).read_bytes() == b'Example question?'
    other = library.upload('lesson.txt', b'Example question?', 'Networks', 'Tema 2')
    assert other['id'] != first['id'] and len(library.list_files()) == 2


@pytest.mark.parametrize('suffix', ['.docx', '.pptx'])
def test_office_text_is_available_to_study_tools(suffix):
    data = office_file(suffix, '<root><p><t>Explain a router?</t></p></root>')
    result = library.upload('lesson' + suffix, data, 'Networks', 'Routers')
    assert 'Explain a router?' in result['text']
    assert not result['warning']


def test_pdf_and_image_are_saved_with_honest_text_warnings():
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(stream)
    pdf = library.upload('scan.pdf', stream.getvalue())
    assert pdf['mime'] == 'application/pdf' and 'No readable text' in pdf['warning']
    picture = io.BytesIO()
    Image.new('RGB', (10, 10)).save(picture, format='PNG')
    png = library.upload('picture.png', picture.getvalue())
    assert png['text'] == '' and 'OCR is not available' in png['warning']


@pytest.mark.parametrize('name,data', [
    ('page.html', b'<script>bad()</script>'),
    ('empty.txt', b''), ('fake.pdf', b'not a PDF'),
    ('fake.png', b'not a picture'), ('fake.docx', b'not a ZIP'),
    ('binary.txt', b'a\x00b'), ('bad.txt', b'\xff\x81\x80'),
])
def test_invalid_files_leave_no_library_or_material_records(name, data):
    with pytest.raises(ValueError):
        library.upload(name, data)
    assert library.list_files() == [] and store.rows('materials') == []
    assert list((store.DATA / 'library').iterdir()) == []


def test_size_limit_and_text_clipping(monkeypatch):
    monkeypatch.setattr(library, 'MAX_BYTES', 100)
    with pytest.raises(ValueError, match='20 MB'):
        library.upload('large.txt', b'a' * 101)
    monkeypatch.setattr(library, 'MAX_BYTES', 100000)
    text = library.upload('long.md', b'a' * 25000)
    assert len(text['text']) == 24000 and '24,000' in text['warning']


def test_compressed_bomb_and_xml_entities_are_rejected():
    bomb = office_file('.docx', '<root><p><t>' + 'A' * 1000000 + '</t></p></root>')
    with pytest.raises(ValueError, match='compressed'):
        library.upload('bomb.docx', bomb)
    entity = office_file('.docx', '<!DOCTYPE x [<!ENTITY a "boom">]><root>&a;</root>')
    with pytest.raises(ValueError, match='XML entities'):
        library.upload('entities.docx', entity)
    assert library.list_files() == []


@pytest.mark.parametrize('file_id', ['../../outside', 'unknown', '0' * 32])
def test_file_lookup_cannot_escape_library(file_id):
    with pytest.raises(ValueError):
        library.get(file_id)
    with pytest.raises(ValueError):
        library.file_path(file_id)


def test_database_failure_does_not_leave_an_original_or_partial_record(monkeypatch):
    # A conflicting material UUID exercises rollback after the library insert.
    library.upload('existing.txt', b'original')
    monkeypatch.setattr(library, 'uuid4', lambda: type('ID', (), {'hex': 'f' * 32})())
    store.save_material('upload:' + 'f' * 32, '', 'collision', '', '')
    with pytest.raises(sqlite3.IntegrityError):
        library.upload('new.txt', b'new material')
    assert len(library.list_files()) == 1
    assert not (store.DATA / 'library' / ('f' * 32 + '.txt')).exists()


def test_uuid_collision_never_overwrites_an_original(monkeypatch):
    result = library.upload('original.txt', b'Keep this')
    monkeypatch.setattr(library, 'uuid4', lambda: type('ID', (), {'hex': result['id']})())
    with pytest.raises(FileExistsError):
        library.upload('other.txt', b'Different content')
    assert library.file_path(result['id']).read_bytes() == b'Keep this'


def test_utf16_text_and_encrypted_pdf():
    text = library.upload('utf16.txt', 'Çfarë është rrjeti?'.encode('utf-16'))
    assert text['text'] == 'Çfarë është rrjeti?'
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt('secret')
    stream = io.BytesIO()
    writer.write(stream)
    with pytest.raises(ValueError, match='Password-protected'):
        library.upload('locked.pdf', stream.getvalue())
    assert len(library.list_files()) == 1
