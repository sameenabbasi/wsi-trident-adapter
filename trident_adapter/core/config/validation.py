import os
from pathlib import Path
from typing import Any


def _is_int_like(x: Any) -> bool:
    try:
        return int(x) == x
    except Exception:
        return False


def validate_yaml_structure(raw: Any) -> list[str]:
    errors: list[str] = []

    if raw is None:
        return errors

    if not isinstance(raw, dict):
        errors.append("YAML root must be a dict.")
        return errors

    allowed_sections = {"io", "segmentation", "patching", "features", "normalization", "system"}
    
    for sec, val in raw.items():
        if sec not in allowed_sections:
            errors.append(f"Unknown section: {sec}")
            continue

        if not isinstance(val, dict):
            errors.append(f"Section '{sec}' must be a dict.")

    return errors


def validate_config(config: dict) -> list[str]:
    """
    Quick validation for essential config fields.
    Not exhaustive; meant to catch common mistakes early.

    Returns
    -------
    list of str
        Human-readable error messages. Empty list means OK.
    """
    errors: list[str] = []

    # io.wsi_dir
    wsi_dir = config["io"]["wsi_dir"]
    if not os.path.exists(wsi_dir):
        errors.append(f"io.wsi_dir does not exist: {Path(wsi_dir).resolve()}")

    # segmentation.segmenter
    valid_segmenters = {"hest", "grandqc"}
    segm = config["segmentation"]["segmenter"]
    if segm not in valid_segmenters:
        errors.append(
            f"Invalid segmentation.segmenter '{segm}'. "
            "Acceptable: 'hest' or 'grandqc'."
        )

    # segmentation.seg_conf_thresh ((0,1))
    seg_thr = config["segmentation"]["seg_conf_thresh"]
    try:
        seg_thr_f = float(seg_thr)
        if not (0.0 < seg_thr_f < 1.0):
            errors.append(
                f"Invalid segmentation.seg_conf_thresh {seg_thr_f}. "
                "Must be in (0, 1). Recommended: 0.4 or 0.5 for H&E."
            )

    except Exception:
        errors.append(
            "segmentation.seg_conf_thresh must be a float in (0,1); got"
            f" {seg_thr!r}"
        )

    # patching.magnification
    valid_mags = {5, 10, 20, 40, 80}
    mag = config["patching"]["magnification"]
    if mag not in valid_mags:
        errors.append(
            f"Invalid patching.magnification {mag}. "
            "Acceptable: {5, 10, 20, 40, 80}."
        )

    # patching.patch_size (int >= 1)
    ps = config["patching"]["patch_size"]
    if not _is_int_like(ps) or int(ps) < 1:
        errors.append(
            f"Invalid patching.patch_size {ps}. "
            "Must be integer >= 1. Recommended: {224, 256, 512, 1024}."
        )

    else:
        ps = int(ps)

        # patching.overlap (int >= 0 and < patch_size)
        ov = config["patching"]["overlap"]
        if not _is_int_like(ov):
            errors.append(
                f"Invalid patching.overlap {ov}. Must be integer >= 0 and <"
                " patch_size."
            )

        else:
            ov = int(ov)
            if not (0 <= ov < ps):
                errors.append(
                    f"Invalid patching.overlap {ov}. Must be >= 0 and <"
                    f" patch_size ({ps})."
                )

    # patching.min_tissue_proportion ([0,1])
    mtp = config["patching"]["min_tissue_proportion"]
    try:
        mtp_f = float(mtp)
        if not (0.0 <= mtp_f <= 1.0):
            errors.append(
                f"Invalid patching.min_tissue_proportion {mtp_f}. "
                "Must be in [0, 1]. Recommended: 0."
            )

    except Exception:
        errors.append(
            "patching.min_tissue_proportion must be a number in [0,1]; got"
            f" {mtp!r}"
        )

    # features.encoder
    valid_encoders = {
        "conch_v1",
        "conch_v15",
        "uni_v1",
        "uni_v2",
        "ctranspath",
        "phikon",
        "phikon_v2",
        "resnet50",
        "gigapath",
        "hoptimus0",
        "kaiko-vits8",
        "kaiko-vits16",
        "kaiko-vitb8",
        "kaiko-vitb16",
        "kaiko-vitl14",
        "lunit-vits8",
    }

    enc = config["features"]["encoder"]
    if enc not in valid_encoders:
        errors.append(
            f"Invalid features.encoder '{enc}'. "
            "Please refer to the config instructions for acceptable inputs."
        )

        # normalization
    norm = config.get("normalization", {})
    if not isinstance(norm.get("enabled", False), bool):
        errors.append("normalization.enabled must be true or false.")

    if norm.get("method", "macenko") not in {"macenko"}:
        errors.append(
            "Invalid normalization.method. Currently supported: 'macenko'."
        )

    if not norm.get("output_dir", "./out/normalized"):
        errors.append("normalization.output_dir must not be empty.")
        
    return errors
