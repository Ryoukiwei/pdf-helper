import json
from dataclasses import dataclass
from pathlib import Path

from pdf_img_tool.crop_gui import run_crop
from pdf_img_tool.models import CropBox, CropConfig, ManifestSource, OutputFormat, OutputRules
from pdf_img_tool.utils import ensure_dir

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SESSION_FILE_NAME = "crop_session.json"

@dataclass(slots=True)
class CropJob:
    input_path: Path | None
    output_path: Path | None
    source: str
    skip_reason: str | None


@dataclass(slots=True)
class HistoryEntry:
    index: int
    action: str
    output_path: Path | None
    prev_box: CropBox | None


def normalize_subdir_name(raw: str) -> str:
    return raw.strip().strip("/")


def output_suffix_for(input_path: Path, output_format: OutputFormat | None) -> str:
    if output_format == "png":
        return ".png"
    if output_format == "jpeg":
        return ".jpg"
    return input_path.suffix.lower()


def build_output_path(input_path: Path, out_dir: Path, output_rules: OutputRules) -> Path:
    suffix = output_suffix_for(input_path, output_rules.output_format)
    target_dir = out_dir
    if output_rules.out_subdir:
        target_dir = out_dir / output_rules.out_subdir
    return target_dir / f"{input_path.stem}__crop{suffix}"


def pre_crop_skip_reason(
    input_path: Path,
    output_path: Path,
    *,
    overwrite: bool,
) -> str | None:
    if "__crop" in input_path.stem:
        return "input already appears cropped (__crop in filename)"
    if output_path.exists() and not overwrite:
        return "output exists and --no-overwrite is active"
    return None


def resolve_manifest_image_path(
    raw_path: str,
    *,
    manifest_path: Path,
    manifest_out_dir: Path,
) -> Path | None:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None

    paths_to_try = (manifest_out_dir / candidate, manifest_path.parent / candidate)
    for path in paths_to_try:
        if path.is_file():
            return path.resolve()

    return None


def get_manifest_out_dir(payload: dict[str, object], manifest_path: Path) -> Path:
    raw_out_dir = payload.get("out_dir")
    if isinstance(raw_out_dir, str | Path):
        manifest_out_dir = Path(raw_out_dir).expanduser()
    else:
        manifest_out_dir = manifest_path.parent
    if not manifest_out_dir.is_absolute():
        manifest_out_dir = (manifest_path.parent / manifest_out_dir).resolve()
    return manifest_out_dir


def parse_manifest_candidates(
    item: dict[str, object], source: ManifestSource
) -> tuple[list[tuple[str, str]], str | None]:
    extracted_images = item.get("extracted_images")
    rendered_image = item.get("rendered")
    files = item.get("files")
    method = str(item.get("method", "")).lower()

    extracted: list[str] = []
    rendered: list[str] = []

    if isinstance(extracted_images, list):
        extracted = [str(value) for value in extracted_images if str(value)]
    elif method == "extract" and isinstance(files, list):
        extracted = [str(value) for value in files if str(value)]

    if isinstance(rendered_image, str) and rendered_image:
        rendered = [rendered_image]
    elif method == "render" and isinstance(files, list):
        rendered = [str(value) for value in files if str(value)]

    if source == "extracted":
        if extracted:
            return [(path, "extracted") for path in extracted], None
        return [], "missing extracted_images"

    if source == "rendered":
        if rendered:
            return [(path, "rendered") for path in rendered], None
        return [], "missing rendered image"

    if extracted:
        return [(path, "extracted") for path in extracted], None
    if rendered:
        return [(path, "rendered") for path in rendered], None
    if isinstance(files, list):
        fallback = [str(value) for value in files if str(value)]
        if fallback:
            return [(path, "files") for path in fallback], None

    return [], "no candidate image in manifest item"


def plan_crop_jobs_from_manifest_payload(
    payload: dict[str, object],
    *,
    manifest_path: Path,
    out_dir: Path,
    source: ManifestSource,
    output_rules: OutputRules,
) -> list[CropJob]:
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise SystemExit(f"Invalid manifest format: {manifest_path}")

    manifest_out_dir = get_manifest_out_dir(payload, manifest_path)
    jobs: list[CropJob] = []
    seen_inputs: set[Path] = set()

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            jobs.append(
                CropJob(
                    input_path=None,
                    output_path=None,
                    source="manifest",
                    skip_reason=f"item {idx}: invalid manifest entry",
                )
            )
            continue

        manifest_item: dict[str, object] = {str(key): value for key, value in item.items()}
        candidates, missing_reason = parse_manifest_candidates(manifest_item, source)
        if not candidates:
            jobs.append(
                CropJob(
                    input_path=None,
                    output_path=None,
                    source="manifest",
                    skip_reason=f"item {idx}: {missing_reason}",
                )
            )
            continue

        for raw_path, source_tag in candidates:
            resolved = resolve_manifest_image_path(
                raw_path,
                manifest_path=manifest_path,
                manifest_out_dir=manifest_out_dir,
            )
            if resolved is None:
                jobs.append(
                    CropJob(
                        input_path=None,
                        output_path=None,
                        source=source_tag,
                        skip_reason=f"item {idx}: file not found: {raw_path}",
                    )
                )
                continue

            if resolved.suffix.lower() not in IMAGE_EXTENSIONS:
                jobs.append(
                    CropJob(
                        input_path=resolved,
                        output_path=None,
                        source=source_tag,
                        skip_reason=f"item {idx}: unsupported extension: {resolved.suffix}",
                    )
                )
                continue

            if resolved in seen_inputs:
                continue
            seen_inputs.add(resolved)

            output_path = build_output_path(resolved, out_dir, output_rules)
            reason = pre_crop_skip_reason(
                resolved,
                output_path,
                overwrite=output_rules.overwrite,
            )
            jobs.append(
                CropJob(
                    input_path=resolved,
                    output_path=output_path,
                    source=source_tag,
                    skip_reason=reason,
                )
            )

    return jobs


def plan_crop_jobs_from_manifest(
    manifest_path: Path,
    *,
    out_dir: Path,
    source: ManifestSource,
    output_rules: OutputRules,
) -> list[CropJob]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid manifest format: {manifest_path}")
    return plan_crop_jobs_from_manifest_payload(
        payload,
        manifest_path=manifest_path,
        out_dir=out_dir,
        source=source,
        output_rules=output_rules,
    )


def collect_images_from_dir(images_dir: Path) -> list[Path]:
    if not images_dir.exists() or not images_dir.is_dir():
        raise SystemExit(f"Image directory not found: {images_dir}")

    return [
        path
        for path in sorted(images_dir.iterdir(), key=lambda p: p.name.lower())
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def plan_crop_jobs_from_paths(
    image_paths: list[Path],
    *,
    out_dir: Path,
    output_rules: OutputRules,
    source: str,
) -> list[CropJob]:
    jobs: list[CropJob] = []
    for path in image_paths:
        output_path = build_output_path(path, out_dir, output_rules)
        reason = pre_crop_skip_reason(path, output_path, overwrite=output_rules.overwrite)
        jobs.append(
            CropJob(
                input_path=path,
                output_path=output_path,
                source=source,
                skip_reason=reason,
            )
        )
    return jobs


def print_job_plan(jobs: list[CropJob]) -> None:
    if not jobs:
        print("No jobs planned.")
        return

    crop_count = sum(1 for job in jobs if job.skip_reason is None)
    skip_count = len(jobs) - crop_count

    for index, job in enumerate(jobs, start=1):
        status = "SKIP" if job.skip_reason else "CROP"
        source = f" [{job.source}]" if job.source else ""
        target = str(job.input_path) if job.input_path else "-"

        if status == "SKIP":
            reason = job.skip_reason or "invalid job"
            print(f"{index:04d} {status:<4} {target}{source} :: {reason}")
            continue

        if job.output_path is None:
            print(f"{index:04d} SKIP {target}{source} :: invalid job")
            continue

        print(f"{index:04d} {status:<4} {target}{source} -> {job.output_path}")

    print(f"Planned: total={len(jobs)} crop={crop_count} skip={skip_count}")


def serialize_crop_box(crop_box: CropBox | None) -> dict[str, int] | None:
    if crop_box is None:
        return None
    return {
        "left": crop_box.left,
        "top": crop_box.top,
        "right": crop_box.right,
        "bottom": crop_box.bottom,
    }


def parse_int(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def parse_crop_box(payload: object) -> CropBox | None:
    if not isinstance(payload, dict):
        return None

    normalized_payload: dict[str, object] = {
        str(key): value for key, value in payload.items()
    }
    required = ("left", "top", "right", "bottom")
    if any(key not in normalized_payload for key in required):
        return None

    left = parse_int(normalized_payload["left"])
    top = parse_int(normalized_payload["top"])
    right = parse_int(normalized_payload["right"])
    bottom = parse_int(normalized_payload["bottom"])

    if left is None or top is None or right is None or bottom is None:
        return None

    return CropBox(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
    ).normalized()


def session_file_path(out_dir: Path) -> Path:
    return out_dir / SESSION_FILE_NAME


def load_session(
    out_dir: Path,
    *,
    source_label: str,
    total: int,
) -> dict[str, object] | None:
    path = session_file_path(out_dir)
    if not path.exists() or not path.is_file():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None

    if payload.get("source") != source_label:
        return None
    payload_total = parse_int(payload.get("total"))
    if payload_total != total:
        return None

    return payload


def get_session_int(payload: dict[str, object], key: str, default: int) -> int:
    parsed = parse_int(payload.get(key))
    if parsed is None:
        return default
    return parsed


def write_session(
    out_dir: Path,
    *,
    source_label: str,
    total: int,
    next_index: int,
    completed: int,
    skipped: int,
    last_crop_box: CropBox | None,
) -> None:
    ensure_dir(out_dir)
    payload = {
        "version": 1,
        "source": source_label,
        "total": total,
        "next_index": next_index,
        "completed": completed,
        "skipped": skipped,
        "last_crop_box": serialize_crop_box(last_crop_box),
    }
    session_file_path(out_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_session(out_dir: Path) -> None:
    path = session_file_path(out_dir)
    if path.exists() and path.is_file():
        path.unlink()


def run_single_crop(
    *,
    input_path: Path,
    output_path: Path,
    output_rules: OutputRules,
    auto_trim_threshold: int,
    auto_trim_padding: int,
) -> int:
    if not input_path.exists() or not input_path.is_file():
        raise SystemExit(f"Input image not found: {input_path}")

    skip_reason = pre_crop_skip_reason(
        input_path,
        output_path,
        overwrite=output_rules.overwrite,
    )
    if skip_reason:
        print(f"Skip: {input_path} ({skip_reason})")
        return 0

    result = run_crop(
        input_path=input_path,
        output_path=output_path,
        progress_text="1/1",
        allow_back=False,
        auto_trim_threshold=auto_trim_threshold,
        auto_trim_padding=auto_trim_padding,
        output_format=output_rules.output_format,
        jpeg_quality=output_rules.jpeg_quality,
    )

    if result.action == "ok" and result.output_path is not None:
        print(f"Saved cropped image: {result.output_path}")
        return 0

    if result.action == "skip":
        print("Skipped cropping.")
        return 0

    print("Crop cancelled.")
    return 0


def run_batch_crop(
    jobs: list[CropJob],
    out_dir: Path,
    *,
    source_label: str,
    carry_box_enabled: bool,
    auto_trim_threshold: int,
    auto_trim_padding: int,
    output_rules: OutputRules,
) -> int:
    if not jobs:
        raise SystemExit("No images found to crop.")

    ensure_dir(out_dir)

    static_skips = 0
    active_jobs: list[CropJob] = []
    for job in jobs:
        if job.skip_reason:
            static_skips += 1
            name = str(job.input_path) if job.input_path else "manifest-entry"
            print(f"[Skip] {name}: {job.skip_reason}")
            continue
        if job.input_path is None or job.output_path is None:
            static_skips += 1
            print("[Skip] manifest-entry: invalid job")
            continue
        active_jobs.append(job)

    if not active_jobs:
        clear_session(out_dir)
        print(f"Summary: saved=0, skipped={len(jobs)}, total={len(jobs)}")
        return 0

    total = len(active_jobs)
    completed = 0
    skipped = 0
    index = 0
    carry_box: CropBox | None = None
    history: list[HistoryEntry] = []

    existing_session = load_session(out_dir, source_label=source_label, total=total)
    if existing_session is not None:
        index = max(0, min(get_session_int(existing_session, "next_index", 0), total))
        completed = max(0, get_session_int(existing_session, "completed", 0))
        skipped = max(0, get_session_int(existing_session, "skipped", 0))
        carry_box = parse_crop_box(existing_session.get("last_crop_box"))
        if index > 0:
            print(f"Resume session: continue from image {index + 1}/{total}")

    while index < total:
        job = active_jobs[index]
        image_path = job.input_path
        output_path = job.output_path
        if image_path is None or output_path is None:
            skipped += 1
            index += 1
            continue

        title = f"Crop Image ({index + 1}/{total}): {image_path.name}"
        result = run_crop(
            input_path=image_path,
            output_path=output_path,
            window_title=title,
            progress_text=f"{index + 1}/{total}",
            initial_crop_box=carry_box if carry_box_enabled else None,
            allow_back=True,
            auto_trim_threshold=auto_trim_threshold,
            auto_trim_padding=auto_trim_padding,
            output_format=output_rules.output_format,
            jpeg_quality=output_rules.jpeg_quality,
        )

        if result.action == "ok" and result.output_path is not None:
            history.append(
                HistoryEntry(
                    index=index,
                    action="ok",
                    output_path=result.output_path,
                    prev_box=carry_box,
                )
            )
            completed += 1
            if carry_box_enabled:
                carry_box = result.crop_box or carry_box
            index += 1
            write_session(
                out_dir,
                source_label=source_label,
                total=total,
                next_index=index,
                completed=completed,
                skipped=skipped,
                last_crop_box=carry_box,
            )
            print(f"[{index}/{total}] Saved: {result.output_path}")
            continue

        if result.action == "skip":
            history.append(
                HistoryEntry(
                    index=index,
                    action="skip",
                    output_path=None,
                    prev_box=carry_box,
                )
            )
            skipped += 1
            index += 1
            write_session(
                out_dir,
                source_label=source_label,
                total=total,
                next_index=index,
                completed=completed,
                skipped=skipped,
                last_crop_box=carry_box,
            )
            print(f"[{index}/{total}] Skipped: {image_path.name}")
            continue

        if result.action == "back":
            if not history:
                print("[Back] No previous image in current session.")
                continue

            previous = history.pop()
            index = previous.index
            carry_box = previous.prev_box

            if previous.action == "ok":
                completed = max(0, completed - 1)
                if previous.output_path and previous.output_path.exists():
                    previous.output_path.unlink()
            elif previous.action == "skip":
                skipped = max(0, skipped - 1)

            write_session(
                out_dir,
                source_label=source_label,
                total=total,
                next_index=index,
                completed=completed,
                skipped=skipped,
                last_crop_box=carry_box,
            )
            print(f"[Back] Return to image {index + 1}/{total}")
            continue

        write_session(
            out_dir,
            source_label=source_label,
            total=total,
            next_index=index,
            completed=completed,
            skipped=skipped,
            last_crop_box=carry_box,
        )
        print(f"[{index + 1}/{total}] Cancelled by user. Keeping completed outputs.")
        print(f"Summary: saved={completed}, skipped={skipped + static_skips}, total={len(jobs)}")
        return 0

    clear_session(out_dir)
    print(f"Summary: saved={completed}, skipped={skipped + static_skips}, total={len(jobs)}")
    return 0


def run_crop_batch_jobs(
    *,
    jobs: list[CropJob],
    out_dir: Path,
    source_label: str,
    dry_run: bool,
    carry_box_enabled: bool,
    auto_trim_threshold: int,
    auto_trim_padding: int,
    output_rules: OutputRules,
) -> int:
    if dry_run:
        print_job_plan(jobs)
        return 0

    return run_batch_crop(
        jobs,
        out_dir,
        source_label=source_label,
        carry_box_enabled=carry_box_enabled,
        auto_trim_threshold=auto_trim_threshold,
        auto_trim_padding=auto_trim_padding,
        output_rules=output_rules,
    )


def run_crop_command(config: CropConfig) -> int:
    input_path = config.input.expanduser().resolve() if config.input else None
    output_path = config.output.expanduser().resolve() if config.output else None
    manifest_path = config.manifest.expanduser().resolve() if config.manifest else None
    images_dir = config.directory.expanduser().resolve() if config.directory else None
    out_dir = config.out_dir.expanduser().resolve() if config.out_dir else None
    output_rules = config.output_rules

    if input_path is not None:
        if output_path is None:
            raise SystemExit("--output is required when using --input")
        return run_single_crop(
            input_path=input_path,
            output_path=output_path,
            output_rules=output_rules,
            auto_trim_threshold=config.auto_trim_threshold,
            auto_trim_padding=config.auto_trim_padding,
        )

    if manifest_path is not None:
        if not manifest_path.exists() or not manifest_path.is_file():
            raise SystemExit(f"Manifest not found: {manifest_path}")
        if out_dir is None:
            raise SystemExit("--out-dir is required when using --manifest")

        jobs = plan_crop_jobs_from_manifest(
            manifest_path,
            out_dir=out_dir,
            source=config.source,
            output_rules=output_rules,
        )
        source_label = f"manifest:{manifest_path}:{config.source}"
        return run_crop_batch_jobs(
            jobs=jobs,
            out_dir=out_dir,
            source_label=source_label,
            dry_run=config.dry_run,
            carry_box_enabled=config.carry_box,
            auto_trim_threshold=config.auto_trim_threshold,
            auto_trim_padding=config.auto_trim_padding,
            output_rules=output_rules,
        )

    if images_dir is not None:
        if out_dir is None:
            raise SystemExit("--out-dir is required when using --dir")
        images = collect_images_from_dir(images_dir)
        jobs = plan_crop_jobs_from_paths(
            images,
            out_dir=out_dir,
            output_rules=output_rules,
            source="dir",
        )
        source_label = f"dir:{images_dir}"
        return run_crop_batch_jobs(
            jobs=jobs,
            out_dir=out_dir,
            source_label=source_label,
            dry_run=config.dry_run,
            carry_box_enabled=config.carry_box,
            auto_trim_threshold=config.auto_trim_threshold,
            auto_trim_padding=config.auto_trim_padding,
            output_rules=output_rules,
        )

    raise SystemExit("Please provide one source: --input or --manifest or --dir")
