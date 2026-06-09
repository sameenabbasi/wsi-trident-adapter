from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import trident_adapter


def _copy_manifest(src_json: Path, module_path: str) -> None:
    spec = importlib.util.find_spec(module_path)
    if spec is None or spec.origin is None:
        raise RuntimeError(f"Cannot locate module '{module_path}'")
    target_dir = Path(spec.origin).resolve().parent
    shutil.copy2(src_json, target_dir / "local_ckpts.json")


def copy_ckpts(profile: str) -> None:
    adapter_root = Path(trident_adapter.__file__).resolve().parent
    src_profile = adapter_root / "profiles" / profile
    ckpt_dir = src_profile / "local_ckpts"

    if not src_profile.is_dir():
        raise RuntimeError(f"Profile directory not found: {src_profile}")

    if not ckpt_dir.is_dir():
        raise RuntimeError(
            f"Profile '{profile}' does not contain a local_ckpts/ directory:"
            f" {ckpt_dir}"
        )

    mappings: list[tuple[str, str]] = [
        ("segmentation_ckpts.json", "trident.segmentation_models.load"),
        ("patch_encoder_ckpts.json", "trident.patch_encoder_models.load"),
        ("slide_encoder_ckpts.json", "trident.slide_encoder_models.load"),
    ]

    for filename, module_path in mappings:
        src_json = ckpt_dir / filename
        if not src_json.exists():
            continue

        _copy_manifest(src_json, module_path)
