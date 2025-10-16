import trident
from trident.patch_encoder_models.load import (
    encoder_factory as patch_encoder_model_factory,
)
from trident.slide_encoder_models.load import (
    encoder_factory as slide_encoder_model_factory,
)
from ..utils.config.structures import Config


def run_feature_extraction(config: Config, processor: trident.Processor):
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
