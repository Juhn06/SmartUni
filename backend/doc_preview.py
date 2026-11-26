"""Convert common office/image files to HTML (or viewer hints) for in-app preview."""
from __future__ import annotations

import html
from pathlib import Path


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
XLSX_EXTS = {".xlsx", ".xlsm"}
PPTX_EXTS = {".pptx"}
# Older binary formats: offer download-only note
LEGACY_EXTS = {".doc", ".xls", ".ppt"}


def classify_ext(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in PDF_EXTS:
        return "pdf"
    if ext in DOCX_EXTS:
        return "docx"
    if ext in XLSX_EXTS:
        return "xlsx"
    if ext in PPTX_EXTS:
        return "pptx"
    if ext in LEGACY_EXTS:
        return "legacy"
    return "other"


def preview_payload(path: str | Path, original_filename: str) -> dict:
    """Return preview payload for UI.

    kind: image|pdf|html|pptx|xlsx|legacy|other
    pptx includes slides[] for carousel viewer.
    """
    path = Path(path)
    title = original_filename or path.name
    kind = classify_ext(title)
    if kind in ("image", "pdf"):
        return {"kind": kind, "title": title, "html": None, "slides": None}
    if kind == "docx":
        return {"kind": "html", "title": title, "html": _docx_html(path), "slides": None}
    if kind == "xlsx":
        return {"kind": "xlsx", "title": title, "html": _xlsx_html(path), "slides": None}
    if kind == "pptx":
        slides = _pptx_slides(path)
        html_all = "".join(
            f"<section class='ops-slide-preview' data-slide='{i}'>"
            f"<h3>Slide {i}</h3>{s['html']}</section>"
            for i, s in enumerate(slides, 1)
        )
        return {
            "kind": "pptx",
            "title": title,
            "html": html_all or "<p><em>(Không có slide)</em></p>",
            "slides": slides,
            "slide_count": len(slides),
        }
    if kind == "legacy":
        return {
            "kind": "legacy",
            "title": title,
            "html": (
                "<p>Định dạng cũ (.doc/.xls/.ppt) chưa xem trực tiếp được. "
                "Vui lòng tải xuống hoặc chuyển sang .docx / .xlsx / .pptx.</p>"
            ),
            "slides": None,
        }
    return {
        "kind": "other",
        "title": title,
        "html": "<p>Không hỗ trợ xem trước định dạng này. Hãy tải file về máy.</p>",
        "slides": None,
    }


def _docx_html(path: Path) -> str:
    try:
        from docx import Document
    except ImportError:
        return "<p>Thiếu thư viện python-docx.</p>"
    doc = Document(str(path))
    parts: list[str] = []
    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if text:
            style = (p.style.name or "") if p.style else ""
            tag = "h3" if "Heading" in style else "p"
            parts.append(f"<{tag}>{html.escape(text)}</{tag}>")
    for ti, table in enumerate(doc.tables, 1):
        parts.append(f"<h4>Bảng {ti}</h4><div class='ops-table-wrap'><table class='ops-table'>")
        for row in table.rows:
            parts.append("<tr>")
            for cell in row.cells:
                parts.append(f"<td>{html.escape(cell.text or '')}</td>")
            parts.append("</tr>")
        parts.append("</table></div>")
    return "".join(parts) or "<p><em>(Tài liệu trống)</em></p>"


def _xlsx_html(path: Path) -> str:
    try:
        from openpyxl import load_workbook
    except ImportError:
        return "<p>Thiếu thư viện openpyxl.</p>"
    wb = load_workbook(str(path), data_only=True, read_only=True)
    parts: list[str] = []
    for sheet in wb.worksheets[:8]:
        parts.append(f"<h3 class='ops-sheet-title'>{html.escape(sheet.title)}</h3>")
        parts.append("<div class='ops-table-wrap ops-xlsx-wrap'><table class='ops-table'>")
        max_rows = 120
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i >= max_rows:
                parts.append(
                    f"<tr><td colspan='24'><em>… cắt còn {max_rows} dòng đầu</em></td></tr>"
                )
                break
            parts.append("<tr>")
            for cell in row[:24]:
                val = "" if cell is None else str(cell)
                tag = "th" if i == 0 else "td"
                parts.append(f"<{tag}>{html.escape(val)}</{tag}>")
            parts.append("</tr>")
        parts.append("</table></div>")
    wb.close()
    return "".join(parts) or "<p><em>(Workbook trống)</em></p>"


def _pptx_slides(path: Path) -> list[dict]:
    try:
        from pptx import Presentation
    except ImportError:
        return [{"title": "Error", "html": "<p>Thiếu thư viện python-pptx.</p>"}]
    prs = Presentation(str(path))
    slides: list[dict] = []
    for i, slide in enumerate(prs.slides, 1):
        texts: list[str] = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False):
                for para in shape.text_frame.paragraphs:
                    t = (para.text or "").strip()
                    if t:
                        texts.append(t)
            elif hasattr(shape, "text"):
                t = (shape.text or "").strip()
                if t:
                    texts.append(t)
        if texts:
            title = texts[0][:120]
            body = "".join(
                f"<p class='ops-slide-line{' ops-slide-title-line' if j == 0 else ''}'>"
                f"{html.escape(t)}</p>"
                for j, t in enumerate(texts)
            )
        else:
            title = f"Slide {i}"
            body = "<p class='ops-slide-empty'><em>(Không có chữ trên slide)</em></p>"
        slides.append({"index": i, "title": title, "html": body})
    return slides
