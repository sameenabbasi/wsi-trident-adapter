from pathlib import Path

import pandas as pd

from ...utils.io import list_slide_paths
from .structures import ProcessList


def load_and_validate_process_list(
    path: Path | str,
    wsi_dir: Path | str,
    exts: tuple[str, ...] = (".svs", ".tif", ".tiff"),
) -> ProcessList:
    """Load and validate a process list CSV.

    Ensures the file contains a ``wsi`` column and optional ``threshold``/``mpp``
    columns, enforcing an all-or-nothing policy for each optional column. The
    returned dataframe always includes ``wsi`` and only adds ``threshold`` and
    ``mpp`` when the input provided them.
    """

    # Load CSV and verify required columns
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError("process_list has no rows")

    if "wsi" not in df.columns:
        raise ValueError("process_list must contain a 'wsi' column")

    has_threshold = "threshold" in df.columns
    has_mpp = "mpp" in df.columns

    # Normalise wsi column
    df = df.copy()
    df["wsi"] = df["wsi"].astype(str).str.strip()

    if df["wsi"].eq("").any():
        raise ValueError("process_list contains empty wsi values")

    if df["wsi"].duplicated().any():
        raise ValueError("process_list contains duplicate wsi values")

    slides = list_slide_paths(Path(wsi_dir), exts=exts)

    for slide_id in df["wsi"]:
        if slide_id not in slides:
            raise ValueError(f"wsi '{slide_id}' not found under {wsi_dir}")

    selected_columns = ["wsi"]

    # Validate threshold column
    if has_threshold:
        threshold_series = df["threshold"].astype(str).str.strip()
        if threshold_series.eq("").any():
            raise ValueError(
                "threshold column contains blank entries; provide all values or"
                " drop the column."
            )

        try:
            df["threshold"] = threshold_series.astype(float)
        except ValueError as err:
            raise ValueError(
                "threshold column contains non-numeric values"
            ) from err

        if not ((0.0 < df["threshold"]) & (df["threshold"] < 1.0)).all():
            raise ValueError(
                "threshold values must lie in the open interval (0, 1)"
            )

        selected_columns.append("threshold")

    # Validate mpp column
    if has_mpp:
        mpp_series = df["mpp"].astype(str).str.strip()
        if mpp_series.eq("").any():
            raise ValueError(
                "mpp column contains blank entries; provide all values or drop"
                " the column."
            )

        try:
            df["mpp"] = mpp_series.astype(float)
        except ValueError as err:
            raise ValueError("mpp column contains non-numeric values") from err

        selected_columns.append("mpp")

    return ProcessList(
        df=df[selected_columns], has_threshold=has_threshold, has_mpp=has_mpp
    )


def create_default_process_list(
    wsi_dir: Path | str,
    default_threshold: float,
    exts: tuple[str, ...] = (".svs", ".tif", ".tiff"),
) -> ProcessList:
    """Return a process list filled from config defaults (wsi + threshold)."""

    slides = list_slide_paths(wsi_dir, exts=exts)
    df = pd.DataFrame({
        "wsi": list(slides.keys()),
        "threshold": [default_threshold] * len(slides),
    })

    return ProcessList(df=df, has_threshold=True, has_mpp=False)
