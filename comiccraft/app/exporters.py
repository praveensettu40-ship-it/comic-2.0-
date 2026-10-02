"""Step 5 - export the finished comic as a PDF (uses the fpdf2 library)."""
import os
import re
from datetime import datetime
from typing import List

from fpdf import FPDF
from PIL import Image

from .config import EXPORTS_DIR, FONT_BOLD, FONT_ITALIC, FONT_REGULAR

_FONT_NAME = "DejaVu"

# Characters the built-in fallback font cannot print -> simple ASCII versions
_ASCII_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " ",
}


def _clean(text: str) -> str:
    """Remove emoji / unsupported symbols that no PDF font can show."""
    text = (text or "").replace("\r", "")
    return re.sub(r"[\U00010000-\U0010FFFF]", "", text)


def _to_latin1(text: str) -> str:
    for old, new in _ASCII_MAP.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


class _Fonts:
    """Keeps track of which font family/styles are available."""

    def __init__(self, pdf: FPDF):
        self.pdf = pdf
        self.unicode = FONT_REGULAR.exists()
        self.has_bold = False
        self.has_italic = False

        if self.unicode:
            pdf.add_font(_FONT_NAME, "", str(FONT_REGULAR))
            if FONT_BOLD.exists():
                pdf.add_font(_FONT_NAME, "B", str(FONT_BOLD))
                self.has_bold = True
            if FONT_ITALIC.exists():
                pdf.add_font(_FONT_NAME, "I", str(FONT_ITALIC))
                self.has_italic = True
            self.family = _FONT_NAME
        else:
            print("[PDF] static/fonts/DejaVuSans.ttf not found - using Helvetica (basic characters only).")
            self.family = "Helvetica"
            self.has_bold = True
            self.has_italic = True

    def use(self, size: int, bold: bool = False, italic: bool = False) -> None:
        style = ""
        if bold and self.has_bold:
            style += "B"
        if italic and self.has_italic:
            style += "I"
        self.pdf.set_font(self.family, style, size)

    def text(self, value: str) -> str:
        value = _clean(value)
        return value if self.unicode else _to_latin1(value)


def save_pdf(layout: List[dict]) -> str:
    """Compile the comic layout into a multi-page PDF (one panel per page).

    Args:
        layout: The list returned by build_comic_layout().

    Returns:
        The full file path of the saved PDF (inside static/exports).
    """
    if not layout:
        raise ValueError("Cannot export an empty comic layout.")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    fonts = _Fonts(pdf)

    for panel in layout:
        pdf.add_page()

        # ---- panel title ----
        fonts.use(15, bold=True)
        pdf.set_text_color(20, 20, 20)
        title = f"Panel {panel.get('panel', '')}: {panel.get('title', '')}"
        pdf.multi_cell(0, 9, fonts.text(title), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # ---- image ----
        image_path = panel.get("image_path") or ""
        if image_path and os.path.exists(image_path):
            with Image.open(image_path) as img:
                width_px, height_px = img.size
            image_w = min(pdf.epw, 120.0)
            image_h = image_w * height_px / max(1, width_px)

            # keep room for the text underneath; shrink the image if needed
            room = pdf.h - pdf.get_y() - pdf.b_margin - 70
            if image_h > room > 40:
                image_w *= room / image_h
                image_h = room

            x = (pdf.w - image_w) / 2
            y = pdf.get_y()
            pdf.image(image_path, x=x, y=y, w=image_w, h=image_h)
            pdf.set_y(y + image_h + 6)
        else:
            fonts.use(11, italic=True)
            pdf.multi_cell(0, 8, fonts.text(f"[Image missing: {image_path}]"), align="L", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

        # ---- scene description ----
        scene = (panel.get("scene_description") or "").strip()
        if scene:
            fonts.use(11, italic=True)
            pdf.set_text_color(90, 90, 90)
            pdf.multi_cell(0, 6, fonts.text(scene), align="L", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

        # ---- story text ----
        story_text = (panel.get("text") or "").strip()
        if story_text:
            fonts.use(12)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 6.5, fonts.text(story_text), align="L", new_x="LMARGIN", new_y="NEXT")

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = EXPORTS_DIR / f"comic_{timestamp}.pdf"
    pdf.output(str(pdf_path))
    return str(pdf_path)
