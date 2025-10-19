from datetime import datetime, timezone
from pathlib import Path

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
JOB_METADATA_DIR = Path("job_metadata") / RUN_ID


def list_slide_paths(
    wsi_dir: Path | str, exts: tuple[str, ...] = (".svs", ".tif", ".tiff")
) -> dict[str, Path]:
    """Return slide paths keyed by relative filename (including extension)."""

    base_dir = Path(wsi_dir)
    allowed_exts = tuple(ext.lower() for ext in exts)

    slides: dict[str, Path] = {}
    for entry in base_dir.iterdir():
        if entry.name.startswith("._"):
            continue

        if not entry.is_file():
            continue

        if entry.suffix.lower() not in allowed_exts:
            continue

        slide_key = entry.name
        if slide_key in slides:
            raise ValueError(
                "Duplicate slide filename detected: "
                f"'{slide_key}'. Ensure filenames are unique."
            )

        slides[slide_key] = entry.resolve()

    return slides
