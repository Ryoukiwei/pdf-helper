from dataclasses import dataclass
from pathlib import Path
from typing import Literal

CropAction = Literal["ok", "skip", "cancel", "back"]
ExtractMode = Literal["auto", "extract", "render"]
ManifestSource = Literal["auto", "extracted", "rendered"]
OutputFormat = Literal["png", "jpeg"]


@dataclass(slots=True)
class OutputItem:
    page: int
    method: str
    files: list[str]


@dataclass(slots=True)
class CropBox:
    left: int
    top: int
    right: int
    bottom: int

    def normalized(self) -> "CropBox":
        return CropBox(
            left=min(self.left, self.right),
            top=min(self.top, self.bottom),
            right=max(self.left, self.right),
            bottom=max(self.top, self.bottom),
        )

    def is_valid(self) -> bool:
        normalized = self.normalized()
        return normalized.right > normalized.left and normalized.bottom > normalized.top


@dataclass(slots=True)
class CropResult:
    action: CropAction
    output_path: Path | None = None
    crop_box: CropBox | None = None


@dataclass(slots=True)
class ExtractConfig:
    input_pdf: Path
    output: Path
    dpi: int
    mode: ExtractMode
    min_bytes: int
    zip: bool
    zip_path: Path | None


@dataclass(slots=True)
class OutputRules:
    output_format: OutputFormat | None
    jpeg_quality: int
    overwrite: bool
    out_subdir: str


@dataclass(slots=True)
class CropConfig:
    input: Path | None
    output: Path | None
    manifest: Path | None
    directory: Path | None
    out_dir: Path | None
    source: ManifestSource
    dry_run: bool
    carry_box: bool
    auto_trim_threshold: int
    auto_trim_padding: int
    output_rules: OutputRules


@dataclass(slots=True)
class PipelineConfig:
    input_pdf: Path
    output: Path
    dpi: int
    mode: ExtractMode
    min_bytes: int
    crop: bool
    source: ManifestSource
    dry_run: bool
    carry_box: bool
    auto_trim_threshold: int
    auto_trim_padding: int
    output_rules: OutputRules
