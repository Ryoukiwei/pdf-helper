# pdf-helper

[![Python](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CLI](https://img.shields.io/badge/interface-Typer-009688)](https://typer.tiangolo.com/)
[![Formatter: Ruff](https://img.shields.io/badge/style-ruff-1D9BF0)](https://docs.astral.sh/ruff/)

A PDF image workflow tool built with Python 3.12. 📄🖼️

It provides:
- `extract`: extract embedded images from PDF, with render fallback
- `crop`: interactive image crop (single or batch)
- `pipeline`: extract + crop in one command

## ✨ Features

- Fast PDF image extraction with fallback page rendering
- Interactive crop GUI with zoom/pan/rotate/auto-trim
- Batch crop workflow with session resume support
- One-step extract + crop pipeline command

## 📦 Requirements

- Python 3.12+
- `uv`
- Desktop environment for GUI crop (tkinter window)

Dependencies are managed in `pyproject.toml`.

## 🚀 Quick Start

```bash
uv sync
uv run pdf-img --help
```

## 🛠️ CLI Overview

```bash
uv run pdf-img --help
uv run pdf-img extract --help
uv run pdf-img crop --help
uv run pdf-img pipeline --help
```

### Shell Completion (Typer)

```bash
# bash/zsh/fish/powershell are supported
uv run pdf-img --install-completion
uv run pdf-img --show-completion
```

## 📤 Extract Command

Extract images from PDF and generate a manifest JSON.

```bash
uv run pdf-img extract /path/to/sample.pdf -o out --mode auto
```

Common options:
- `pdf` or `--input`: input PDF path
- `-o, --output`: output directory (default: `out_images`)
- `--mode`: `auto` / `extract` / `render`
- `--dpi`: render DPI for page rendering (default: `300`)
- `--min-bytes`: ignore tiny extracted images unless they are the only result
- `--zip`: also create zip archive
- `--zip-path`: custom zip output path

## ✂️ Crop Command

Interactive cropping with tkinter canvas drag-select.

GUI controls:
- Buttons: `Back`, `Redo`, `Rotate Left`, `Rotate Right`, `Auto Trim`, `Skip`, `Cancel`, `OK`
- Keyboard:
  - `Enter` = OK
  - `R` = Redo
  - `T` = Auto Trim
  - `Ctrl+Left` = Rotate Left
  - `Ctrl+Right` = Rotate Right
  - `S` = Skip
  - `B` = Back (batch mode)
  - `Esc` = Cancel
- Zoom and pan:
  - Mouse wheel = zoom in/out
  - Hold `Space` + drag = pan
  - Middle mouse drag = pan
- Selection tuning:
  - Arrow keys = move selection (`Shift` = 10px step)
  - `Alt + Arrow` = resize one edge
  - `[` / `]` = shrink / expand box

### Auto Trim Behavior

- On each image open, GUI computes a suggested crop box.
- If `--carry-box` is enabled and prior box exists, carry-box is used first.
- Otherwise, auto-trim suggestion is used as initial box.
- `Auto Trim` button recalculates and applies bbox with current threshold/padding.

### Single Image Crop

```bash
uv run pdf-img crop --input in/page1.png --output out/page1__crop.png
```

### Batch Crop from Manifest

```bash
uv run pdf-img crop --manifest out/sample_manifest.json --out-dir out
```

### Batch Crop from Directory

```bash
uv run pdf-img crop --dir out/images --out-dir out
```

Supported input extensions: `.jpg`, `.jpeg`, `.png`.

### Crop Options

- Source and preview:
  - `--source auto|extracted|rendered` (manifest mode)
  - `--dry-run` print planned jobs and skip GUI
- Selection behavior:
  - `--carry-box / --no-carry-box`
  - `--auto-trim-threshold <0-255>`
  - `--auto-trim-padding <pixels>`
- Output rules:
  - `--format png|jpeg` (default: keep input extension)
  - `--jpeg-quality <1-100>` (jpeg only)
  - `--overwrite / --no-overwrite` (default: `--no-overwrite`)
  - `--out-subdir <name>` place outputs under `--out-dir/<name>/`

### Batch Behavior Notes

- `__crop` in input filename is skipped automatically.
- If output file exists and `--no-overwrite`, job is skipped and printed.
- Session state is saved in `crop_session.json` under output directory.
- Rerun same batch command to resume from session.

## 🔁 Pipeline Command

Run extract and crop in one command.

```bash
uv run pdf-img pipeline input.pdf -o out
```

Useful examples:

```bash
# Preview crop plan only (no GUI)
uv run pdf-img pipeline input.pdf -o out --dry-run

# Force rendered images in crop stage
uv run pdf-img pipeline input.pdf -o out --source rendered

# Produce jpeg outputs with quality and subdir
uv run pdf-img pipeline input.pdf -o out --format jpeg --jpeg-quality 85 --out-subdir cropped
```

## 🗂️ Project Structure

```text
src/pdf_img_tool/
  typer_app.py  # Typer CLI entrypoint and command routing
  cli.py        # compatibility wrapper
  extract.py    # PDF extract
  crop.py       # crop planning and workflow (single + batch)
  crop_gui.py   # tkinter GUI interaction
  crop_core.py  # crop math and image processing helpers
  pipeline.py   # extract + crop pipeline command
  models.py     # dataclasses / typed models
  utils.py      # shared utility helpers
```

## 📝 Notes

- GUI crop requires a local graphical session.
- On headless environments, GUI crop cannot open a window.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE). ⚖️
