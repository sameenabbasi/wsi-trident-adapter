from __future__ import annotations

from typing import TYPE_CHECKING

from ..utils.config.structures import Config

if TYPE_CHECKING:
    import trident


def run_patching(config: Config, processor: "trident.Processor"):
    coords_dir = (
        f"{config.patching.magnification}x_"
        f"{config.patching.patch_size}px_"
        f"{config.patching.overlap}px_overlap"
    )

    processor.run_patching_job(
        target_magnification=config.patching.magnification,
        patch_size=config.patching.patch_size,
        overlap=config.patching.overlap,
        saveto=coords_dir,
        min_tissue_proportion=config.patching.min_tissue_proportion,
    )
