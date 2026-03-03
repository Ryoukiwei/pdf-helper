from pdf_img_tool.crop import (
    plan_crop_jobs_from_manifest,
    run_crop_batch_jobs,
)
from pdf_img_tool.extract import run_extract
from pdf_img_tool.models import ExtractConfig, PipelineConfig
from pdf_img_tool.utils import safe_stem


def run_pipeline(config: PipelineConfig) -> int:
    pdf_path = config.input_pdf.expanduser().resolve()
    out_dir = config.output.expanduser().resolve()

    extract_config = ExtractConfig(
        input_pdf=pdf_path,
        output=out_dir,
        dpi=config.dpi,
        mode=config.mode,
        min_bytes=config.min_bytes,
        zip=False,
        zip_path=None,
    )
    extract_exit = run_extract(extract_config)
    if extract_exit != 0:
        return extract_exit

    if not config.crop:
        return 0

    manifest_path = out_dir / f"{safe_stem(pdf_path.stem)}_manifest.json"
    jobs = plan_crop_jobs_from_manifest(
        manifest_path,
        out_dir=out_dir,
        source=config.source,
        output_rules=config.output_rules,
    )

    return run_crop_batch_jobs(
        jobs=jobs,
        out_dir=out_dir,
        source_label=f"pipeline:{manifest_path}:{config.source}",
        dry_run=config.dry_run,
        carry_box_enabled=config.carry_box,
        auto_trim_threshold=config.auto_trim_threshold,
        auto_trim_padding=config.auto_trim_padding,
        output_rules=config.output_rules,
    )
