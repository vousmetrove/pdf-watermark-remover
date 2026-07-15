"""
PDF Watermark Remover — Core Algorithm
======================================
Removes light watermarks from scanned PDFs and enhances text sharpness.

Algorithm:
  1. Render each page at the target DPI
  2. Pixels where min(R,G,B) > threshold → set to pure white (watermark removal)
  3. Apply levels stretch: pixel/threshold * 255 * boost (sharpen + brighten)

Usage:
  from core import remove_watermark
  remove_watermark("input.pdf", "output.pdf")

  # CLI: python core.py input.pdf [output.pdf]
"""

import fitz  # PyMuPDF
import numpy as np


def remove_watermark(
    input_path: str,
    output_path: str = None,
    threshold: int = 230,
    dpi: int = 250,
    boost: float = 1.10,
    on_progress=None,
):
    """
    Remove light watermarks from a scanned PDF.

    Args:
        input_path:  Path to input PDF
        output_path: Path to output PDF (default: input stem + '_clean.pdf')
        threshold:   Gray level above which pixels are treated as watermark (0-255)
        dpi:         Output resolution
        boost:       Contrast boost factor (1.0 = no boost, 1.15 = strong)
        on_progress: Callback(current_page, total_pages) for progress reporting
    """
    if output_path is None:
        stem = input_path.rsplit(".", 1)[0]
        output_path = f"{stem}_clean.pdf"

    doc = fitz.open(input_path)
    out = fitz.open()
    n = len(doc)

    for i, page in enumerate(doc):
        if on_progress:
            on_progress(i + 1, n)

        # Render page at target DPI
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n).astype(np.float32)

        # Watermark removal: pixels where all channels > threshold → pure white
        mask = arr.min(axis=2) > threshold
        arr[mask] = [255, 255, 255]

        # Levels stretch: pull shadows toward black, highlights toward white
        arr = np.clip(arr / threshold * 255 * boost, 0, 255).astype(np.uint8)

        # Write to output PDF
        new_pix = fitz.Pixmap(fitz.csRGB, pix.w, pix.h, arr.tobytes(), False)
        out_page = out.new_page(width=page.rect.width, height=page.rect.height)
        out_page.insert_image(out_page.rect, pixmap=new_pix)

    out.save(output_path, garbage=4, deflate=True)
    doc.close()
    out.close()

    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python core.py input.pdf [output.pdf]")
        sys.exit(1)

    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Processing: {src}")
    result = remove_watermark(src, dst, on_progress=lambda cur, tot: print(f"  Page {cur}/{tot}"))
    print(f"Done → {result}")
