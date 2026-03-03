import zipfile
from pathlib import Path


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_stem(name: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in name)


def write_zip_archive(out_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out_dir.glob("*")):
            if path.is_file() and path != zip_path:
                archive.write(path, arcname=path.name)
