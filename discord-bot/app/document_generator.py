"""Document generator module for creating report PDFs with image grids."""

from datetime import date
from pathlib import Path

from fpdf import FPDF, XPos, YPos
from PIL import Image


# Page layout constants (A4 in mm)
PAGE_WIDTH = 210
PAGE_HEIGHT = 297
MARGIN = 10
GRID_COLS = 3
GRID_GAP = 2

CELL_WIDTH = (PAGE_WIDTH - 2 * MARGIN - (GRID_COLS - 1) * GRID_GAP) / GRID_COLS


class _ReportPDF(FPDF):
    """Internal PDF subclass with custom header styling."""

    def header(self):
        # No automatic header; we draw our own per page
        pass


def generate_pdf(
    report_id: str,
    report_date: date,
    roadway: str | None,
    grouped_data: dict,
    output_path: str,
):
    """
    Generate a PDF report for a single (tower_id, report_date, roadway) group.

    Parameters
    ----------
    report_id : str
        The tower id (e.g. "Tower 123").
    report_date : date
        The report date from photo metadata.
    roadway : str | None
        The roadway (e.g. "Jalur Purwakarta - Banyuwangi"), or None.
    grouped_data : dict
        Mapping of sub_id -> list of message dicts.
        Each message dict has keys: "message_id", "images" (list of local file paths).
    output_path : str
        Where to write the resulting PDF file.
    """
    pdf = _ReportPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=MARGIN)

    # ── Title ──
    pdf.set_font("Helvetica", "B", 16)
    if roadway:
        title = f"Progress report {report_id} - {roadway} - {report_date}"
    else:
        title = f"Progress report {report_id} - {report_date}"
    pdf.cell(0, 12, title, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # ── Sections per sub-id ──
    for sub_id, messages in grouped_data.items():
        # Check if we need a new page for the section header
        if pdf.get_y() > PAGE_HEIGHT - MARGIN - 30:
            pdf.add_page()

        # Sub-id header
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, sub_id, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

        # Collect all images for this sub-id
        all_images = []
        for msg in messages:
            all_images.extend(msg.get("images", []))

        # Draw images in grid
        _draw_image_grid(pdf, all_images)

        pdf.ln(6)

    pdf.output(output_path)


def _draw_image_grid(pdf: FPDF, image_paths: list[str]):
    """Draw images in a 3-column grid layout."""
    if not image_paths:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, "(tidak ada gambar)", ln=True)
        return

    x_start = MARGIN
    y_start = pdf.get_y()
    col = 0
    row_height = 0

    for img_path in image_paths:
        if not Path(img_path).exists():
            continue

        # Get image dimensions
        with Image.open(img_path) as img:
            orig_w, orig_h = img.size

        # Calculate scaled height maintaining aspect ratio
        scale_h = CELL_WIDTH * orig_h / orig_w
        max_cell_height = 80  # mm, prevent overly tall images
        cell_h = min(scale_h, max_cell_height)

        # Check if we need a new page
        if y_start + cell_h > PAGE_HEIGHT - MARGIN:
            pdf.add_page()
            y_start = pdf.get_y()
            col = 0
            row_height = 0

        # Calculate x position
        x = x_start + col * (CELL_WIDTH + GRID_GAP)
        y = y_start

        # Place image
        pdf.image(img_path, x=x, y=y, w=CELL_WIDTH, h=0)  # h=0 keeps aspect ratio

        # Track row height
        row_height = max(row_height, cell_h)

        col += 1
        if col >= GRID_COLS:
            col = 0
            y_start += row_height + GRID_GAP
            row_height = 0

    # Advance cursor past the last row
    if col > 0:
        y_start += row_height + GRID_GAP

    pdf.set_y(y_start)
