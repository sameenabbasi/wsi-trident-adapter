from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import trident_adapter


def _trident_root() -> Path:
    # find_spec on the top-level package never imports it
    spec = importlib.util.find_spec("trident")
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError("Cannot locate the 'trident' package")
    return Path(next(iter(spec.submodule_search_locations))).resolve()


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

    trident = _trident_root()

    # maps source JSON → directory inside trident where local_ckpts.json lives
    mappings: list[tuple[str, Path]] = [
        ("segmentation_ckpts.json", trident / "segmentation_models" / "load.py"),
        ("patch_encoder_ckpts.json", trident / "patch_encoder_models" / "load.py"),
        ("slide_encoder_ckpts.json", trident / "slide_encoder_models" / "load.py"),
    ]

    for filename, target_load_py in mappings:
        src_json = ckpt_dir / filename
        if not src_json.exists():
            continue

        if not target_load_py.parent.is_dir():
            raise RuntimeError(
                f"Expected trident subpackage directory not found:"
                f" {target_load_py.parent}"
            )

        shutil.copy2(src_json, target_load_py.parent / "local_ckpts.json")
