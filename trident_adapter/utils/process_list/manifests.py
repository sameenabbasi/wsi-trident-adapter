from __future__ import annotations

from pathlib import Path
from .structures import ProcessList

import pandas as pd


def group_process_list_to_manifest(
    process_list: ProcessList,
    manifest_dir: Path | str,
    threshold_precision: int = 2,
) -> tuple[dict[float, Path], Path]:
    """Group validated process list rows by threshold and write manifests."""

    df = process_list.df

    manifest_base = Path(manifest_dir)
    manifest_base.mkdir(parents=True, exist_ok=True)

    threshold_to_manifest_path: dict[float, Path] = {}
    manifest_columns = ["wsi"] + (["mpp"] if process_list.has_mpp else [])

    if process_list.has_threshold:
        grouped: dict[float, pd.DataFrame] = {}
        for rounded, group in df.groupby(
            df["threshold"].apply(
                lambda val: round(float(val), threshold_precision)
            )
        ):
            grouped[rounded] = group

        for threshold, group in grouped.items():
            manifest_name = f"threshold-{threshold:.{threshold_precision}f}.csv"
            manifest_path = manifest_base / manifest_name
            group[manifest_columns].to_csv(manifest_path, index=False)
            threshold_to_manifest_path[threshold] = manifest_path

    all_manifest_path = manifest_base / "all.csv"
    df[manifest_columns].to_csv(all_manifest_path, index=False)

    return threshold_to_manifest_path, all_manifest_path
