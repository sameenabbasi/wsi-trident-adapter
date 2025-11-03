from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.config.structures import Config

if TYPE_CHECKING:
    import trident


def run_segmentation(
    config: Config,
    processor: "trident.Processor",
    seg_conf_override: float | None = None,
):
    from trident.segmentation_models.load import segmentation_model_factory

    conf_thresh = (
        seg_conf_override
        if seg_conf_override is not None
        else config.segmentation.seg_conf_thresh
    )

    segmentation_model = segmentation_model_factory(
        config.segmentation.segmenter,
        confidence_thresh=conf_thresh,
    )

    if config.segmentation.remove_artifacts:
        artifact_remover_model = segmentation_model_factory("grandqc_artifact")
    else:
        artifact_remover_model = None

    processor.run_segmentation_job(
        segmentation_model,
        seg_mag=segmentation_model.target_mag,
        device=config.system.device,
        holes_are_tissue=not config.segmentation.remove_holes,
        artifact_remover_model=artifact_remover_model,
    )
