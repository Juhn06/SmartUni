"""
Generate PowerPoint (PPTX) from summary/analysis text.
Produces fully editable .pptx files for download and offline use.

PPTX generation inspired by Edit-Banana:
  https://github.com/BIT-DataLab/Edit-Banana
  "Universal Content Re-Editor: Make the Uneditable, Editable"
"""
import re
from io import BytesIO

from pptx import Presentation
from pptx.util import Inches, Pt


def _strip_markdown(text: str) -> str:
    """Remove basic markdown formatting for plain text in slides."""
    if not text:
        return ""
    # Remove **bold**, *italic*, __bold__, _italic_
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # Remove ### headers (keep text)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    return text.strip()


def _split_into_slides(text: str, max_chars: int = 400) -> list[str]:
    """Split text into slide-sized chunks (paragraphs preferred, then by length)."""
    if not text or not text.strip():
        return []
    text = _strip_markdown(text)
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    slides = []
    current = []
    current_len = 0
    for p in paras:
        if current_len + len(p) + 2 > max_chars and current:
            slides.append("\n\n".join(current))
            current = [p]
            current_len = len(p)
        else:
            current.append(p)
            current_len += len(p) + 2
    if current:
        slides.append("\n\n".join(current))
    return slides


def build_pptx(title: str, content: str, source_type: str = "Summary") -> bytes:
    """
    Build a PPTX presentation from title and content text.
    Returns raw bytes of the .pptx file.
    """
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    # Title slide
    slide_layout = prs.slide_layouts[6]  # blank
    slide = prs.slides.add_slide(slide_layout)
    left, top, width, height = Inches(0.5), Inches(2.5), Inches(9), Inches(1.5)
    tx = slide.shapes.add_textbox(left, top, width, height)
    tf = tx.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title[:200]
    p.font.size = Pt(44)
    p.font.bold = True
    if source_type:
        p2 = tf.add_paragraph()
        p2.text = source_type
        p2.font.size = Pt(18)
        p2.space_before = Pt(12)

    # Content slides
    chunks = _split_into_slides(content)
    for chunk in chunks:
        slide = prs.slides.add_slide(slide_layout)
        left, top, width, height = Inches(0.5), Inches(0.5), Inches(9), Inches(6.5)
        tx = slide.shapes.add_textbox(left, top, width, height)
        tf = tx.text_frame
        tf.word_wrap = True
        lines = chunk.split("\n")
        for i, line in enumerate(lines):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = line[:500]
            p.font.size = Pt(18)
            p.space_after = Pt(6)

    buf = BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()
