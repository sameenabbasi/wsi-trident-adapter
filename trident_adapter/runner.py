from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, TYPE_CHECKING

from .utils.config.structures import Config
from .utils.process_list.loader import (
    create_default_process_list,
    load_and_validate_process_list,
)
from .utils.process_list.manifests import group_process_list_to_manifest
from .utils.process_list.structures import ProcessList

THRESHOLD_PRECISION = 2

if TYPE_CHECKING:
    import trident


def _initialize_processor(
    config: Config,
    wsi_tmp_dir: str | None = None,
    manifest_path: Path | str | None = None,
) -> "trident.Processor":

    import trident

    try:
        max_workers = len(os.sched_getaffinity(0))
    except AttributeError:
        max_workers = os.cpu_count() or 1

    return trident.Processor(
        job_dir=str(config.io.job_dir),
        wsi_source=str(config.io.wsi_dir),
        wsi_ext=list(config.io.wsi_extension),
        wsi_cache=wsi_tmp_dir,
        clear_cache=True,
        skip_errors=True,
        custom_mpp_keys=None,
        custom_list_of_wsis=str(manifest_path) if manifest_path else None,
        max_workers=max_workers,
    )


def run_pipeline(
    config: Config,
    task: Literal["all", "seg", "patch", "feat"],
):
    from .pipeline.features import run_feature_extraction
    from .pipeline.patching import run_patching
    from .pipeline.segmentation import run_segmentation

    manifest_dir = config.io.job_dir / "job_metadata" / "process_lists"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    if config.io.process_list:
        process_list = load_and_validate_process_list(
            config.io.process_list,
            config.io.wsi_dir,
            exts=config.io.wsi_extension,
        )
    else:
        process_list = create_default_process_list(
            config.io.wsi_dir,
            config.segmentation.seg_conf_thresh,
            exts=config.io.wsi_extension,
        )

    if not process_list.has_threshold:
        df = process_list.df.copy()
        df["threshold"] = config.segmentation.seg_conf_thresh
        process_list = ProcessList(
            df=df,
            has_threshold=True,
            has_mpp=process_list.has_mpp,
        )

    manifest_paths, all_slides_manifest = group_process_list_to_manifest(
        process_list,
        manifest_dir,
        threshold_precision=THRESHOLD_PRECISION,
    )

    # wsi_tmp_dir = os.getenv("WSI_TMP_DIR", None)
    wsi_tmp_dir = None
    

    if task in {"seg", "all"}:
        for threshold, manifest_path in manifest_paths.items():
            processor = _initialize_processor(
                config,
                wsi_tmp_dir=wsi_tmp_dir,
                manifest_path=manifest_path,
            )
            run_segmentation(
                config,
                processor,
                seg_conf_override=threshold,
            )

    if task in {"patch", "all"}:
        processor = _initialize_processor(
            config,
            wsi_tmp_dir=wsi_tmp_dir,
            manifest_path=all_slides_manifest,
        )
        run_patching(config, processor)

    if task in {"feat", "all"}:
        processor = _initialize_processor(
            config,
            wsi_tmp_dir=wsi_tmp_dir,
            manifest_path=all_slides_manifest,
        )
        run_feature_extraction(config, processor)
