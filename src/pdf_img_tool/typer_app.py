from pathlib import Path
from typing import Annotated, Literal

import typer

from pdf_img_tool.crop import normalize_subdir_name, run_crop_command
from pdf_img_tool.extract import run_extract
from pdf_img_tool.models import CropConfig, ExtractConfig, OutputRules, PipelineConfig
from pdf_img_tool.pipeline import run_pipeline

ExtractMode = Literal["auto", "extract", "render"]
ManifestSource = Literal["auto", "extracted", "rendered"]
OutputFormat = Literal["png", "jpeg"]

app = typer.Typer(help="PDF image helper tool")


def resolve_pdf_input(pdf: Path | None, input_pdf: Path | None) -> Path:
    resolved = input_pdf or pdf
    if resolved is None:
        raise typer.BadParameter(
            "input PDF is required (use positional `pdf` or `--input`).",
            param_hint="pdf or --input",
        )
    return resolved


def validate_crop_source(
    input_path: Path | None,
    manifest_path: Path | None,
    directory: Path | None,
    output_path: Path | None,
    out_dir: Path | None,
) -> None:
    selected = sum(value is not None for value in (input_path, manifest_path, directory))
    if selected != 1:
        raise typer.BadParameter(
            "Provide exactly one of --input, --manifest, or --dir.",
            param_hint="--input/--manifest/--dir",
        )

    if input_path is not None and output_path is None:
        raise typer.BadParameter("--output is required when using --input.", param_hint="--output")

    if (manifest_path is not None or directory is not None) and out_dir is None:
        raise typer.BadParameter(
            "--out-dir is required when using --manifest or --dir.",
            param_hint="--out-dir",
        )


@app.command("extract")
def extract_command(
    pdf: Annotated[
        Path | None,
        typer.Argument(help="Input PDF path (same as --input)."),
    ] = None,
    input_pdf: Annotated[
        Path | None,
        typer.Option("-i", "--input", help="Input PDF path.", rich_help_panel="Input"),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="Output directory.", rich_help_panel="Output"),
    ] = Path("out_images"),
    dpi: Annotated[
        int,
        typer.Option(help="DPI used when rendering page to PNG.", rich_help_panel="Format"),
    ] = 300,
    mode: Annotated[
        ExtractMode,
        typer.Option(
            help=(
                "auto: extract first then render fallback; "
                "extract: extract only; render: render only"
            ),
            rich_help_panel="Input",
        ),
    ] = "auto",
    min_bytes: Annotated[
        int,
        typer.Option(
            "--min-bytes",
            help=(
                "Ignore extracted images smaller than this threshold "
                "unless they are the only result."
            ),
            rich_help_panel="Input",
        ),
    ] = 30_000,
    zip_output: Annotated[
        bool,
        typer.Option(
            "--zip", help="Also package output files into a zip archive.", rich_help_panel="Output"
        ),
    ] = False,
    zip_path: Annotated[
        Path | None,
        typer.Option(
            "--zip-path",
            help="Custom output zip path. Defaults to <output_dir>/<pdf_stem>_images.zip.",
            rich_help_panel="Output",
        ),
    ] = None,
) -> None:
    config = ExtractConfig(
        input_pdf=resolve_pdf_input(pdf, input_pdf),
        output=output,
        dpi=dpi,
        mode=mode,
        min_bytes=min_bytes,
        zip=zip_output,
        zip_path=zip_path,
    )
    raise typer.Exit(run_extract(config))


@app.command("crop")
def crop_command(
    input_path: Annotated[
        Path | None,
        typer.Option(
            "--input", help="Input image path for single-image crop.", rich_help_panel="Input"
        ),
    ] = None,
    manifest: Annotated[
        Path | None,
        typer.Option("--manifest", help="Manifest JSON for batch crop.", rich_help_panel="Input"),
    ] = None,
    directory: Annotated[
        Path | None,
        typer.Option(
            "--dir", help="Input directory for batch crop (jpg/jpeg/png).", rich_help_panel="Input"
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Output image path for single-image crop (--input mode).",
            rich_help_panel="Output",
        ),
    ] = None,
    out_dir: Annotated[
        Path | None,
        typer.Option(
            "--out-dir",
            help="Output directory for batch crop (--manifest/--dir mode).",
            rich_help_panel="Output",
        ),
    ] = None,
    source: Annotated[
        ManifestSource,
        typer.Option(
            help="Manifest source strategy: auto prefers extracted and falls back to rendered.",
            rich_help_panel="Batch",
        ),
    ] = "auto",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print planned crop jobs and skip opening GUI.",
            rich_help_panel="Batch",
        ),
    ] = False,
    carry_box: Annotated[
        bool,
        typer.Option(
            "--carry-box/--no-carry-box",
            help="Carry previous crop box to next image in batch mode.",
            rich_help_panel="Batch",
        ),
    ] = False,
    auto_trim_threshold: Annotated[
        int,
        typer.Option(
            "--auto-trim-threshold",
            help="Auto trim threshold (0-255, lower keeps lighter content).",
            rich_help_panel="Auto-trim",
        ),
    ] = 245,
    auto_trim_padding: Annotated[
        int,
        typer.Option(
            "--auto-trim-padding",
            help="Padding in pixels added around auto-trim box.",
            rich_help_panel="Auto-trim",
        ),
    ] = 12,
    output_format: Annotated[
        OutputFormat | None,
        typer.Option(
            "--format",
            help="Output format for cropped images. Default keeps input extension.",
            rich_help_panel="Format",
        ),
    ] = None,
    jpeg_quality: Annotated[
        int,
        typer.Option(
            "--jpeg-quality",
            help="JPEG quality (1-100), used only when --format jpeg.",
            rich_help_panel="Format",
        ),
    ] = 90,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite/--no-overwrite",
            help="Overwrite existing outputs (default: no-overwrite).",
            rich_help_panel="Output",
        ),
    ] = False,
    out_subdir: Annotated[
        str,
        typer.Option(
            "--out-subdir",
            help="Optional subdirectory under --out-dir for cropped files.",
            rich_help_panel="Output",
        ),
    ] = "",
) -> None:
    validate_crop_source(input_path, manifest, directory, output, out_dir)
    config = CropConfig(
        input=input_path,
        output=output,
        manifest=manifest,
        directory=directory,
        out_dir=out_dir,
        source=source,
        dry_run=dry_run,
        carry_box=carry_box,
        auto_trim_threshold=auto_trim_threshold,
        auto_trim_padding=auto_trim_padding,
        output_rules=OutputRules(
            output_format=output_format,
            jpeg_quality=jpeg_quality,
            overwrite=overwrite,
            out_subdir=normalize_subdir_name(out_subdir),
        ),
    )
    raise typer.Exit(run_crop_command(config))


@app.command("pipeline")
def pipeline_command(
    pdf: Annotated[
        Path | None,
        typer.Argument(help="Input PDF path (same as --input)."),
    ] = None,
    input_pdf: Annotated[
        Path | None,
        typer.Option("-i", "--input", help="Input PDF path.", rich_help_panel="Input"),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="Output directory.", rich_help_panel="Output"),
    ] = Path("out_images"),
    dpi: Annotated[
        int,
        typer.Option(help="DPI used when rendering page to PNG.", rich_help_panel="Format"),
    ] = 300,
    mode: Annotated[
        ExtractMode,
        typer.Option(help="Extract mode for first stage.", rich_help_panel="Input"),
    ] = "auto",
    min_bytes: Annotated[
        int,
        typer.Option(
            "--min-bytes",
            help="Ignore tiny extracted images unless they are the only result.",
            rich_help_panel="Input",
        ),
    ] = 30_000,
    crop: Annotated[
        bool,
        typer.Option(
            "--crop/--no-crop", help="Run crop stage after extract.", rich_help_panel="Batch"
        ),
    ] = True,
    source: Annotated[
        ManifestSource,
        typer.Option(
            help="Manifest source strategy for crop stage.",
            rich_help_panel="Batch",
        ),
    ] = "auto",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print planned crop jobs and skip opening GUI.",
            rich_help_panel="Batch",
        ),
    ] = False,
    carry_box: Annotated[
        bool,
        typer.Option(
            "--carry-box/--no-carry-box",
            help="Carry previous crop box to next image in batch mode.",
            rich_help_panel="Batch",
        ),
    ] = False,
    auto_trim_threshold: Annotated[
        int,
        typer.Option(
            "--auto-trim-threshold",
            help="Auto trim threshold (0-255, lower keeps lighter content).",
            rich_help_panel="Auto-trim",
        ),
    ] = 245,
    auto_trim_padding: Annotated[
        int,
        typer.Option(
            "--auto-trim-padding",
            help="Padding in pixels added around auto-trim box.",
            rich_help_panel="Auto-trim",
        ),
    ] = 12,
    output_format: Annotated[
        OutputFormat | None,
        typer.Option(
            "--format",
            help="Output format for cropped images. Default keeps input extension.",
            rich_help_panel="Format",
        ),
    ] = None,
    jpeg_quality: Annotated[
        int,
        typer.Option(
            "--jpeg-quality",
            help="JPEG quality (1-100), used only when --format jpeg.",
            rich_help_panel="Format",
        ),
    ] = 90,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite/--no-overwrite",
            help="Overwrite existing outputs (default: no-overwrite).",
            rich_help_panel="Output",
        ),
    ] = False,
    out_subdir: Annotated[
        str,
        typer.Option(
            "--out-subdir",
            help="Optional subdirectory under --output for cropped files.",
            rich_help_panel="Output",
        ),
    ] = "",
) -> None:
    config = PipelineConfig(
        input_pdf=resolve_pdf_input(pdf, input_pdf),
        output=output,
        dpi=dpi,
        mode=mode,
        min_bytes=min_bytes,
        crop=crop,
        source=source,
        dry_run=dry_run,
        carry_box=carry_box,
        auto_trim_threshold=auto_trim_threshold,
        auto_trim_padding=auto_trim_padding,
        output_rules=OutputRules(
            output_format=output_format,
            jpeg_quality=jpeg_quality,
            overwrite=overwrite,
            out_subdir=normalize_subdir_name(out_subdir),
        ),
    )
    raise typer.Exit(run_pipeline(config))


def main() -> None:
    app()
