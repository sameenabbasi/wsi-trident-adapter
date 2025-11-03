from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.config.structures import Config

if TYPE_CHECKING:
    import trident


def run_feature_extraction(config: Config, processor: "trident.Processor"):
    from trident.patch_encoder_models.load import (
        encoder_factory as patch_encoder_model_factory,
    )

    coords_dir = (
        f"{config.patching.magnification}x_"
        f"{config.patching.patch_size}px_"
        f"{config.patching.overlap}px_overlap"
    )

    encoder = patch_encoder_model_factory(config.features.encoder)
    processor.run_patch_feature_extraction_job(
        coords_dir=coords_dir,
        patch_encoder=encoder,
        device=config.system.device,
        saveas="h5",
        batch_limit=config.features.batch_size,
    )
