"""Local, bounded PDF page previews without a browser PDF plug-in."""
from io import BytesIO
import math
from pathlib import Path
import threading

import pypdfium2 as pdfium


MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_EDGE = 1400
MAX_PIXELS = 4_000_000
# 200 inches is already far larger than a school handout or slide.
MAX_PAGE_UNITS = 14_400
# PDFium is not thread-safe, even when separate documents are used.
_lock = threading.Lock()


def _open(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('The saved PDF is missing. Upload the original again.')
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('PDF previews support files up to 20 MB.')
    return pdfium.PdfDocument(str(path))


def _close(*objects):
    # Close the PIL view before its underlying native bitmap and document.
    for obj in objects:
        if obj is not None:
            try:
                obj.close()
            except Exception:
                pass


def metadata(path: Path):
    """Return the page count of a saved PDF, without extracting its contents."""
    with _lock:
        document = None
        try:
            document = _open(path)
            count = len(document)
            if count < 1:
                raise ValueError('This PDF has no pages to display.')
            return {'pages': count}
        except ValueError:
            raise
        except Exception as error:
            raise ValueError('This PDF could not be opened for preview. It may be damaged or password protected.') from error
        finally:
            _close(document)


def render_page(path: Path, page: int):
    """Return one zero-indexed page as PNG bytes, at most 1400px on an edge."""
    if type(page) is not int or page < 0:
        raise ValueError('Choose a valid PDF page.')
    with _lock:
        document = page_object = bitmap = image = None
        try:
            document = _open(path)
            if page >= len(document):
                raise ValueError('This page does not exist in the PDF.')
            page_object = document[page]
            width, height = page_object.get_size()
            if any(not math.isfinite(v) or v <= 0 or v > MAX_PAGE_UNITS for v in (width, height)):
                raise ValueError('This PDF page has unsupported dimensions. Use the readable text view instead.')
            scale = min(2.0, MAX_EDGE / max(width, height))
            output_width = math.ceil(width * scale)
            output_height = math.ceil(height * scale)
            if output_width * output_height > MAX_PIXELS:
                raise ValueError('This PDF page is too large to preview.')
            # No JavaScript or interactive PDF form environment is initialized.
            bitmap = page_object.render(scale=scale, may_draw_forms=False)
            image = bitmap.to_pil()
            output = BytesIO()
            image.save(output, format='PNG')
            return output.getvalue()
        except ValueError:
            raise
        except Exception as error:
            raise ValueError('This PDF page could not be rendered. Try the readable text view.') from error
        finally:
            _close(image, bitmap, page_object, document)
