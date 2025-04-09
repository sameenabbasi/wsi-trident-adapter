import argparse
import os
import yaml

import trident
from trident.segmentation_models.load import segmentation_model_factory
from trident.patch_encoder_models.load import (
    encoder_factory as patch_encoder_model_factory,
)


def validate_config(config: dict) -> None:
    """
    A quick validation check on the config file.
    Does not validate all parameters and covers all cases.
    """

    # data, wsi_dir
    if not os.path.exists(config["io"]["wsi_dir"]):
        raise Exception(f"Path to WSIs {config['wsi_dir']} does not exist.")

    # segementation, segmenter
    if config["segmentation"]["segmenter"] not in ["hest", "grandqc"]:
        raise Exception(
            f"Invalid segmenter choice {config['segmentation']['segmenter']}. "
            "Acceptable inputs: 'hest' or 'grandqc'.",
        )

    # segementation, seg_conf_thresh
    if not (0 < config["segmentation"]["seg_conf_thresh"] < 1):
        raise Exception(
            "Invalid segmentation confidence threshold"
            f" {config['segmentation']['seg_conf_thresh']}. Acceptable inputs:"
            " (0, 1), Recommended: {0.4, 0.5} for H&E slides."
        )

    # patching, magnification
    if config["patching"]["magnification"] not in [5, 10, 20, 40, 80]:
        raise Exception(
            "Invalid patch magnification "
            f"{config['patching']['magnification']}. "
            "Acceptable inputs: {5, 10, 20, 40, 80}."
        )

    # patching, patch_size
    if (
        int(config["patching"]["patch_size"])
        != config["patching"]["patch_size"]
        or not config["patching"]["patch_size"] >= 1
    ):
        raise Exception(
            f"Invalid patch size {config['patching']['patch_size']}. "
            "Acceptable inputs: Any integer >= 1, "
            "Recommended: {224, 256, 512, 1024}."
        )

    # patching, overlap
    if (
        int(config["patching"]["overlap"]) != config["patching"]["overlap"]
        or not 0
        <= config["patching"]["overlap"]
        < config["patching"]["patch_size"]
    ):
        raise Exception(
            f"Invalid patch overlap {config['patching']['overlap']}. "
            "Acceptable inputs: Any integer >= 0 and < patch size, "
            "Recommended: 0."
        )

    # patching, min_tissue_proportion
    if not (0 <= config["patching"]["min_tissue_proportion"] <= 1):
        raise Exception(
            "Invalid minimum tissue proportion "
            f"{config['patching']['min_tissue_proportion']}. "
            "Acceptable inputs: [0, 1], Recommended: 0."
        )

    # features, encoder
    if config["features"]["encoder"] not in [
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
    ]:
        raise Exception(
            f"Invalid feature encoder {config['features']['encoder']}. "
            "Please refer to the config instructions for acceptable inputs."
        )


def run_segmentation(config: dict, processor: trident.Processor):
    segmentation_model = segmentation_model_factory(
        config["segmentation"]["segmenter"],
        confidence_thresh=args.seg_conf_thresh,
    )

    if config["segmentation"]["remove_artifacts"]:
        artifact_remover_model = segmentation_model_factory("grandqc_artifact")
    else:
        artifact_remover_model = None

    processor.run_segmentation_job(
        segmentation_model,
        seg_mag=segmentation_model.target_mag,
        device=config["system"]["device"],
        holes_are_tissue=not config["segmentation"]["remove_holes"],
        artifact_remover_model=artifact_remover_model,
    )


def run_patching(config: dict, processor: trident.Processor):
    coords_dir = (
        f'{config["patching"]["magnification"]}x_'
        f'{config["patching"]["patch_size"]}px_'
        f'{config["patching"]["overlap"]}px_overlap'
    )

    processor.run_patching_job(
        target_magnification=config["patching"]["magnification"],
        patch_size=config["patching"]["patch_size"],
        overlap=config["patching"]["overlap"],
        saveto=coords_dir,
        min_tissue_proportion=config["patching"]["min_tissue_proportion"],
    )


def run_feature_extraction(config: dict, processor: trident.Processor):
    coords_dir = (
        f'{config["patching"]["magnification"]}x_'
        f'{config["patching"]["patch_size"]}px_'
        f'{config["patching"]["overlap"]}px_overlap'
    )

    encoder = patch_encoder_model_factory(config["features"]["encoder"])
    processor.run_patch_feature_extraction_job(
        coords_dir=coords_dir,
        patch_encoder=encoder,
        device=config["system"]["device"],
        saveas="h5",
        batch_limit=config["features"]["batch_size"],
    )


def initialize_processor(config: dict, wsi_tmp_dir: str) -> trident.Processor:
    return trident.Processor(
        job_dir=config["io"]["job_dir"],
        wsi_source=config["io"]["wsi_dir"],
        wsi_ext=config["io"]["wsi_extension"],
        wsi_cache=wsi_tmp_dir,
        clear_cache=True,
        skip_errors=True,
        custom_mpp_keys=None,
        custom_list_of_wsis=args.custom_list_of_wsis,
    )


def main(args):
    with open(args.config) as f:
        config = yaml.safe_load(f)

    validate_config(config)

    processor = initialize_processor(config, os.environ["WSI_TMP_DIR"])

    if args.task == "seg" or args.task == "all":
        run_segmentation(config, processor)

    if args.task == "patch" or args.task == "all":
        run_patching(config, processor)

    if args.task == "feat" or args.task == "all":
        run_feature_extraction(config, processor)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config", type=str, default="configs/config_template.yaml"
    )

    parser.add_argument(
        "--task",
        type=str,
        default="all",
        choices=["seg", "patch", "feat", "all"],
    )

    args = parser.parse_args()
    main(args)
