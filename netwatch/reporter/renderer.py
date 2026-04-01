"""Render reports as Markdown files and PDFs with embedded charts."""

from __future__ import annotations

import io
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.figure import Figure


_UNICODE_MAP = {
    "\u2014": "-",   # em dash
    "\u2013": "-",   # en dash
    "\u2192": "->",  # →
    "\u2190": "<-",  # ←
    "\u2193": "v",   # ↓
    "\u2191": "^",   # ↑
    "\u00d7": "x",   # ×
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u00b7": ".",
    "\u25b2": "^",
    "\u25bc": "v",
    "\u2265": ">=",
    "\u2264": "<=",
}


def _ascii_safe(text: str) -> str:
    for uni, asc in _UNICODE_MAP.items():
        text = text.replace(uni, asc)
    # Strip any remaining non-latin1 chars
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _fig_to_png_bytes(fig: Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def _build_pdf(markdown_str: str, chart_figs: list[Figure], output_path: Path) -> None:
    """Build a PDF from markdown text + matplotlib figures using fpdf2."""
    from fpdf import FPDF

    class _PDF(FPDF):
        def header(self) -> None:
            pass

        def footer(self) -> None:
            self.set_y(-12)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(150)
            self.cell(0, 10, f"Page {self.page_no()}", align="C")

    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    page_w = pdf.w - pdf.l_margin - pdf.r_margin  # usable width in mm

    # --- Parse and render markdown line-by-line ---
    lines = markdown_str.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        # H1
        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.set_text_color(0, 51, 122)
            pdf.multi_cell(0, 8, _ascii_safe(line[2:].strip()))
            pdf.set_draw_color(0, 102, 204)
            pdf.set_line_width(0.5)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_w, pdf.get_y())
            pdf.ln(3)
            i += 1
            continue

        # H2
        if line.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(0, 51, 122)
            pdf.ln(4)
            pdf.multi_cell(0, 7, _ascii_safe(line[3:].strip()))
            pdf.set_draw_color(180, 200, 220)
            pdf.set_line_width(0.3)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_w, pdf.get_y())
            pdf.ln(2)
            i += 1
            continue

        # Table: collect all consecutive table lines
        if line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            _render_table(pdf, table_lines, page_w)
            pdf.ln(3)
            continue

        # Bold paragraph (starts with **)
        if line.startswith("**") or "**" in line:
            _render_inline(pdf, line, page_w)
            pdf.ln(1)
            i += 1
            continue

        # Horizontal rule or empty separator
        if line.strip() in ("---", "***", "___") or line.strip() == "":
            pdf.ln(2)
            i += 1
            continue

        # Italic / plain paragraph
        if line.strip():
            _render_inline(pdf, line, page_w)
            pdf.ln(1)

        i += 1

    # --- Embed charts ---
    if chart_figs:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(0, 51, 122)
        pdf.cell(0, 8, "Charts", ln=True)
        pdf.set_draw_color(180, 200, 220)
        pdf.set_line_width(0.3)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_w, pdf.get_y())
        pdf.ln(4)

        for fig in chart_figs:
            png_bytes = _fig_to_png_bytes(fig)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(png_bytes)
                tmp_path = tmp.name
            # Fit image to page width, preserve aspect ratio
            import PIL.Image  # type: ignore[import-untyped]
            with PIL.Image.open(tmp_path) as img:
                orig_w, orig_h = img.size
            aspect = orig_h / orig_w
            img_w = page_w
            img_h = img_w * aspect
            if pdf.get_y() + img_h > pdf.h - pdf.b_margin - 15:
                pdf.add_page()
            pdf.image(tmp_path, x=pdf.l_margin, w=img_w, h=img_h)
            pdf.ln(4)
            Path(tmp_path).unlink(missing_ok=True)

    pdf.output(str(output_path))


def _render_table(pdf: object, table_lines: list[str], page_w: float) -> None:
    """Render a markdown pipe-table into the PDF."""
    from fpdf import FPDF
    assert isinstance(pdf, FPDF)

    rows: list[list[str]] = []
    for line in table_lines:
        # Skip separator rows like |---|---|
        if re.match(r"^\|[-| :]+\|$", line.strip()):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)

    if not rows:
        return

    n_cols = max(len(r) for r in rows)
    col_w = page_w / n_cols

    for row_idx, row in enumerate(rows):
        is_header = row_idx == 0
        pdf.set_font("Helvetica", "B" if is_header else "", 8)
        if is_header:
            pdf.set_fill_color(0, 102, 204)
            pdf.set_text_color(255, 255, 255)
        else:
            fill = row_idx % 2 == 0
            pdf.set_fill_color(245, 249, 255) if fill else pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(30, 30, 30)

        # Measure max height needed for this row
        row_h = 6.0
        for cell in row:
            # strip markdown bold markers before measuring
            clean = _ascii_safe(re.sub(r"\*\*(.+?)\*\*", r"\1", cell))
            lines_needed = max(1, len(clean) // max(1, int(col_w / 2.2)))
            row_h = max(row_h, lines_needed * 5.5)

        for j, cell in enumerate(row):
            clean = _ascii_safe(re.sub(r"\*\*(.+?)\*\*", r"\1", cell))
            x0 = pdf.l_margin + j * col_w
            pdf.set_xy(x0, pdf.get_y())
            pdf.multi_cell(
                col_w,
                row_h / max(1, len(clean) // max(1, int(col_w / 2.2)) or 1),
                clean,
                border=1,
                fill=True,
                max_line_height=5.5,
                new_x="RIGHT" if j < n_cols - 1 else "LEFT",
                new_y="TOP" if j < n_cols - 1 else "NEXT",
            )
        pdf.ln(0)

    pdf.set_text_color(0, 0, 0)


def _render_inline(pdf: object, line: str, page_w: float) -> None:  # noqa: ARG001
    """Render a line with **bold** and _italic_ markers."""
    from fpdf import FPDF
    assert isinstance(pdf, FPDF)

    # Strip leading list markers
    line = re.sub(r"^[-*] ", "", line)

    # Split on **bold** and _italic_ tokens
    parts = re.split(r"(\*\*[^*]+\*\*|_[^_]+_)", line)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)

    # Write each part inline; multi_cell resets x so we handle wrapping simply
    full = ""
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            full += part[2:-2]
        elif part.startswith("_") and part.endswith("_"):
            full += part[1:-1]
        else:
            full += part

    # Render as a single multi_cell (bold/italic in-line mixing is complex in fpdf2)
    has_bold = "**" in line
    pdf.set_font("Helvetica", "B" if has_bold else "", 10)
    pdf.set_text_color(0, 51, 122 if has_bold else 30)
    pdf.multi_cell(0, 5.5, _ascii_safe(full.strip()))
    pdf.set_text_color(30, 30, 30)


def save_report(
    markdown_str: str,
    output_dir: Path,
    stem: str,
    chart_figs: list[Figure] | None = None,
) -> tuple[Path, Path]:
    """Write *stem*.md and *stem*.pdf into *output_dir*.

    Returns ``(md_path, pdf_path)``.
    """
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    figs = chart_figs or []

    md_path = output_dir / f"{stem}.md"
    md_path.write_text(markdown_str, encoding="utf-8")

    pdf_path = output_dir / f"{stem}.pdf"
    _build_pdf(markdown_str, figs, pdf_path)

    for fig in figs:
        plt.close(fig)

    return md_path, pdf_path
