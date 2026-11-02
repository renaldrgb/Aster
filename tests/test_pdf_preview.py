from io import BytesIO

from PIL import Image
from pypdf import PdfWriter
import pytest

from src import pdf_preview


def make_pdf(tmp_path, width=612, height=792, pages=1):
    path = tmp_path / 'lesson.pdf'
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=width, height=height)
    with path.open('wb') as handle:
        writer.write(handle)
    return path


def test_metadata_and_png_preview(tmp_path):
    path = make_pdf(tmp_path, pages=2)
    assert pdf_preview.metadata(path) == {'pages': 2}
    result = pdf_preview.render_page(path, 1)
    assert result.startswith(b'\x89PNG\r\n\x1a\n')
    with Image.open(BytesIO(result)) as image:
        assert image.format == 'PNG'
        assert max(image.size) <= pdf_preview.MAX_EDGE
        assert image.width * image.height <= pdf_preview.MAX_PIXELS
        assert abs(image.width / image.height - 612 / 792) < .002
    # Native handles must be released so a saved file can be moved on Windows.
    path.rename(tmp_path / 'moved.pdf')


@pytest.mark.parametrize('page', [-1, 1, 999, True, '0', 0.5])
def test_invalid_pages_are_rejected(tmp_path, page):
    path = make_pdf(tmp_path)
    with pytest.raises(ValueError, match='page'):
        pdf_preview.render_page(path, page)


def test_extreme_page_geometry_is_rejected(tmp_path):
    path = make_pdf(tmp_path, width=20_000, height=20_000)
    with pytest.raises(ValueError, match='dimensions'):
        pdf_preview.render_page(path, 0)


@pytest.mark.parametrize('operation', [pdf_preview.metadata, lambda p: pdf_preview.render_page(p, 0)])
def test_corrupt_and_missing_files_have_readable_errors(tmp_path, operation):
    path = tmp_path / 'broken.pdf'
    path.write_bytes(b'%PDF-1.7\nnot a real PDF')
    with pytest.raises(ValueError, match='PDF'):
        operation(path)
    with pytest.raises(ValueError, match='missing'):
        operation(tmp_path / 'missing.pdf')


def test_resources_close_after_render_failure(monkeypatch, tmp_path):
    closed = []

    class Bitmap:
        def to_pil(self):
            raise RuntimeError('simulated conversion failure')
        def close(self):
            closed.append('bitmap')

    class Page:
        def get_size(self):
            return (612, 792)
        def render(self, **kwargs):
            return Bitmap()
        def close(self):
            closed.append('page')

    class Document:
        def __len__(self):
            return 1
        def __getitem__(self, key):
            return Page()
        def close(self):
            closed.append('document')

    monkeypatch.setattr(pdf_preview, '_open', lambda path: Document())
    with pytest.raises(ValueError, match='rendered'):
        pdf_preview.render_page(tmp_path / 'unused.pdf', 0)
    assert closed == ['bitmap', 'page', 'document']
