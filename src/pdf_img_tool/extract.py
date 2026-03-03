import json
from dataclasses import asdict
from pathlib import Path

import fitz  # PyMuPDF

from pdf_img_tool.models import ExtractConfig, OutputItem
from pdf_img_tool.utils import ensure_dir, safe_stem, write_zip_archive


def extract_images_from_page(
    doc: fitz.Document,
    page_index: int,
    out_dir: Path,
    prefix: str,
) -> list[Path]:
    """Extract embedded images from a page and return saved file paths."""
    page = doc.load_page(page_index)
    images = page.get_images(full=True)
    saved: list[Path] = []
    seen_xref: set[int] = set()

    for image in images:
        xref = image[0]
        if xref in seen_xref:
            continue
        seen_xref.add(xref)

        try:
            base = doc.extract_image(xref)
            img_bytes = base["image"]
            ext = base.get("ext", "bin")
            out_path = out_dir / (f"{prefix}_p{page_index + 1:04d}_img{len(saved) + 1:03d}.{ext}")
            out_path.write_bytes(img_bytes)
            saved.append(out_path)
            continue
        except Exception:
            pass

        try:
            pix = fitz.Pixmap(doc, xref)
            if pix.n - pix.alpha >= 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            out_path = out_dir / (f"{prefix}_p{page_index + 1:04d}_img{len(saved) + 1:03d}.png")
            pix.save(str(out_path))
            saved.append(out_path)
        except Exception:
            continue

    return saved


def render_page_to_png(
    doc: fitz.Document,
    page_index: int,
    out_dir: Path,
    prefix: str,
    dpi: int,
) -> Path:
    """Render a full PDF page to PNG at a fixed DPI."""
    page = doc.load_page(page_index)
    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    out_path = out_dir / f"{prefix}_p{page_index + 1:04d}_render_{dpi}dpi.png"
    pix.save(str(out_path))
    return out_path


def write_manifest(
    out_dir: Path,
    prefix: str,
    pdf_path: Path,
    dpi: int,
    mode: str,
    items: list[OutputItem],
) -> Path:
    manifest = {
        "pdf": str(pdf_path),
        "page_count": len(items),
        "out_dir": str(out_dir),
        "dpi": dpi,
        "mode": mode,
        "items": [asdict(item) for item in items],
    }
    manifest_path = out_dir / f"{prefix}_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def run_extract(config: ExtractConfig) -> int:
    pdf_path = config.input_pdf.expanduser().resolve()
    if not pdf_path.exists() or not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    out_dir = config.output.expanduser().resolve()
    ensure_dir(out_dir)

    prefix = safe_stem(pdf_path.stem)
    mode = config.mode

    results: list[OutputItem] = []
    with fitz.open(str(pdf_path)) as doc:
        for page_index in range(doc.page_count):
            page_files: list[Path] = []
            method_used: str | None = None

            if mode in ("auto", "extract"):
                extracted = extract_images_from_page(doc, page_index, out_dir, prefix)
                extracted_big = [
                    path for path in extracted if path.stat().st_size >= config.min_bytes
                ]
                page_files = extracted_big if extracted_big else extracted
                if page_files:
                    method_used = "extract"

            if mode == "render" or (mode == "auto" and not page_files):
                rendered = render_page_to_png(doc, page_index, out_dir, prefix, config.dpi)
                page_files = [rendered]
                method_used = "render"

            results.append(
                OutputItem(
                    page=page_index + 1,
                    method=method_used or "none",
                    files=[path.name for path in page_files],
                )
            )

    write_manifest(out_dir, prefix, pdf_path, config.dpi, mode, results)

    zip_path: Path | None = None
    if config.zip:
        zip_output_path: Path = (
            config.zip_path.expanduser().resolve()
            if config.zip_path
            else out_dir / f"{prefix}_images.zip"
        )
        write_zip_archive(out_dir, zip_output_path)
        zip_path = zip_output_path

    extracted_pages = sum(1 for item in results if item.method == "extract")
    rendered_pages = sum(1 for item in results if item.method == "render")
    print(f"Done. Pages: {len(results)}, extracted: {extracted_pages}, rendered: {rendered_pages}")
    print(f"Output: {out_dir}")
    if zip_path:
        print(f"ZIP: {zip_path}")

    return 0
