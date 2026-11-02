"""Local schoolwork originals and bounded, untrusted text for study tools."""
import hashlib
import io
from pathlib import Path
import re
import sqlite3
import warnings
import zipfile
from uuid import uuid4

from src import school_reader, store

MAX_BYTES = 20 * 1024 * 1024
MAX_EXPANDED_BYTES = 30 * 1024 * 1024
MIMES = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.txt': 'text/plain', '.md': 'text/markdown',
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
}


def init():
    store.init()
    (store.DATA / 'library').mkdir(parents=True, exist_ok=True)
    with store.db() as connection:
        connection.execute('''CREATE TABLE IF NOT EXISTS library_files (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, course TEXT NOT NULL,
            topic TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL,
            suffix TEXT NOT NULL, digest TEXT NOT NULL, course_key TEXT NOT NULL,
            topic_key TEXT NOT NULL, material_id TEXT UNIQUE NOT NULL,
            warning TEXT NOT NULL, created TEXT NOT NULL,
            UNIQUE(digest, course_key, topic_key))''')


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{32}', value):
        raise ValueError('Schoolwork file not found.')
    return value


def _public(row):
    result = {key: row[key] for key in (
        'id', 'name', 'course', 'topic', 'mime', 'size', 'material_id',
        'warning', 'created')}
    result['text'] = row['body'] or ''
    result['url'] = '/api/library/' + result['id'] + '/file'
    result['content_is_untrusted'] = True
    return result


_SELECT = '''SELECT f.*, m.body FROM library_files f
             LEFT JOIN materials m ON m.id = f.material_id'''


def list_files():
    """Return newest-first metadata and extracted text, never filesystem paths."""
    init()
    with store.db() as connection:
        return [_public(row) for row in connection.execute(_SELECT + ' ORDER BY f.created DESC, f.id')]


def get(file_id):
    """Return one public file record, or raise ValueError when not found."""
    _id(file_id)
    init()
    with store.db() as connection:
        row = connection.execute(_SELECT + ' WHERE f.id=?', (file_id,)).fetchone()
    if row is None:
        raise ValueError('Schoolwork file not found.')
    return _public(row)


def file_path(file_id):
    """Resolve a known UUID to its original, for an authenticated file route."""
    _id(file_id)
    init()
    with store.db() as connection:
        row = connection.execute('SELECT suffix FROM library_files WHERE id=?', (file_id,)).fetchone()
    if row is None or row['suffix'] not in MIMES:
        raise ValueError('Schoolwork file not found.')
    path = store.DATA / 'library' / (file_id + row['suffix'])
    if not path.is_file():
        raise ValueError('The saved schoolwork file is missing. Upload the original again.')
    return path


def _label(value, label):
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ValueError(label + ' must be text.')
    value = ' '.join(value.split())
    if len(value) > 200:
        raise ValueError(label + ' must be 200 characters or fewer.')
    return value


def _validate_archive(data, suffix):
    """Check the complete container, before the existing XML extractor runs."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            required = {'[Content_Types].xml', 'word/document.xml' if suffix == '.docx' else 'ppt/presentation.xml'}
            if not required.issubset(names) or len(names) != len(entries):
                raise ValueError('This is not a valid ' + suffix[1:].upper() + ' document.')
            if len(entries) > 2000 or sum(entry.file_size for entry in entries) > MAX_EXPANDED_BYTES:
                raise ValueError('The expanded document exceeds the safe reading limit (30 MB).')
            for entry in entries:
                if entry.flag_bits & 1:
                    raise ValueError('Password-protected documents cannot be read.')
                if entry.file_size > 8 * 1024 * 1024 or entry.file_size / max(entry.compress_size, 1) > 250:
                    raise ValueError('This document contains an excessively large or compressed entry.')
                if entry.filename.lower().endswith('.xml'):
                    content = archive.read(entry)
                    if b'<!doctype' in content.lower() or b'<!entity' in content.lower():
                        raise ValueError('XML entities are not supported in uploaded documents.')
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ValueError('The document archive is damaged or unsupported.') from exc


def _extract(data, suffix, name):
    if suffix in ('.png', '.jpg', '.jpeg'):
        from PIL import Image
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as picture:
                    expected = 'PNG' if suffix == '.png' else 'JPEG'
                    if picture.format != expected or picture.width * picture.height > 25_000_000:
                        raise ValueError('The image format is incorrect or exceeds 25 megapixels.')
                    picture.verify()
        except Exception as exc:
            raise ValueError('This is not a readable PNG or JPEG image (maximum 25 megapixels).') from exc
        return '', 'Image saved for viewing. OCR is not available; image text cannot be used for questions or quizzes.'
    if suffix in ('.docx', '.pptx'):
        _validate_archive(data, suffix)
    elif suffix == '.pdf':
        if not data.lstrip().startswith(b'%PDF-'):
            raise ValueError('This is not a valid PDF document.')
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValueError('Password-protected PDFs cannot be read. Upload an unlocked copy.')
            if not len(reader.pages):
                raise ValueError('The PDF contains no pages.')
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError('The PDF is damaged and cannot be opened.') from exc
    elif suffix in ('.txt', '.md'):
        try:
            encoding = 'utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
            text = data.decode(encoding)
        except UnicodeError as exc:
            raise ValueError('Save text documents with UTF-8 or UTF-16 encoding and upload again.') from exc
        if any(ord(char) < 32 and char not in '\t\r\n\f' for char in text):
            raise ValueError('This text document contains binary data.')
        # Decode before clipping so valid UTF-16 and large plain text work too.
        warning = 'Only the first 24,000 characters are available to study tools.' if len(text) > school_reader.MAX_TEXT else ''
        return text[:school_reader.MAX_TEXT], warning
    if len(data) > school_reader.MAX_BYTES:
        return '', 'Original saved for viewing. Text extraction is limited to 15 MB; upload a smaller copy to use it in study tools.'
    try:
        result = school_reader.extract_document(data, MIMES[suffix], name)
    except Exception as exc:
        raise ValueError('The document could not be read. Check that it opens correctly and is not password-protected.') from exc
    warning = ''
    if not result['text'].strip():
        warning = 'No readable text was found. The original is saved; scanned pages need OCR before study tools can read them.'
    elif result.get('truncated'):
        warning = 'Text preview is limited to 24,000 characters and 60 PDF pages; the complete original is saved.'
    return result['text'], warning


def upload(filename, data, course='', topic=''):
    """Validate and persist an original plus its study material, without network calls.

    Repeated bytes within the same class/topic return the existing record with
    duplicate=True. Other successes return duplicate=False. Failures raise
    ValueError and never create a partial library or material record.
    """
    if not isinstance(filename, str):
        raise ValueError('Choose a file with a name.')
    name = filename.replace('\\', '/').rsplit('/', 1)[-1].strip()
    if not name or len(name) > 255 or any(ord(char) < 32 for char in name):
        raise ValueError('Choose a valid filename of 255 characters or fewer.')
    suffix = Path(name).suffix.lower()
    if suffix not in MIMES:
        raise ValueError('Upload a PDF, DOCX, PPTX, TXT, MD, PNG, or JPG file.')
    if not isinstance(data, bytes) or not data:
        raise ValueError('The uploaded file is empty.')
    if len(data) > MAX_BYTES:
        raise ValueError('Files must be 20 MB or smaller.')
    course, topic = _label(course, 'Class'), _label(topic, 'Topic')
    digest = hashlib.sha256(data).hexdigest()
    keys = (digest, course.casefold(), topic.casefold())
    init()
    with store.db() as connection:
        existing = connection.execute(_SELECT + ' WHERE f.digest=? AND f.course_key=? AND f.topic_key=?', keys).fetchone()
    if existing:
        # Restore a missing original rather than letting dedup hide a lost file.
        target = store.DATA / 'library' / (existing['id'] + existing['suffix'])
        if not target.exists():
            target.write_bytes(data)
        return {**_public(existing), 'duplicate': True}
    text, warning = _extract(data, suffix, name)
    file_id = uuid4().hex
    material_id = 'upload:' + file_id
    url = '/api/library/' + file_id + '/file'
    created = store.now()
    path = store.DATA / 'library' / (file_id + suffix)
    # Never overwrite another original, even if an ID collision is injected.
    with path.open('xb') as original:
        original.write(data)
    try:
        with store.db() as connection:
            connection.execute('''INSERT INTO library_files
                (id,name,course,topic,mime,size,suffix,digest,course_key,topic_key,material_id,warning,created)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (file_id, name, course, topic, MIMES[suffix], len(data), suffix,
                 *keys, material_id, warning, created))
            # Same fields as save_material; one transaction keeps the file index
            # and study material together if either database write fails.
            connection.execute('INSERT INTO materials(id,course,title,body,url,updated) VALUES(?,?,?,?,?,?)',
                               (material_id, course, topic or Path(name).stem, text, url, created))
    except sqlite3.IntegrityError:
        path.unlink(missing_ok=True)
        with store.db() as connection:
            existing = connection.execute(_SELECT + ' WHERE f.digest=? AND f.course_key=? AND f.topic_key=?', keys).fetchone()
        if existing is None:
            raise
        return {**_public(existing), 'duplicate': True}
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {**get(file_id), 'duplicate': False}
