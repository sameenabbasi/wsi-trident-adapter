from pathlib import Path

import pandas as pd


def list_slide_paths(
    wsi_dir: Path | str, exts: tuple[str, ...] = (".svs", ".tif", ".tiff")
) -> dict[str, Path]:
    """Return slide paths keyed by slide identifier."""

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

        slide_id = entry.stem
        if slide_id in slides:
            raise ValueError(
                "Duplicate slide identifier detected: "
                f"'{slide_id}'. Ensure filenames are unique."
            )

        slides[slide_id] = entry.resolve()

    return slides



