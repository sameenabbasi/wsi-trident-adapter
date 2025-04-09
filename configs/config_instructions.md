# WSI Pipeline Configuration Guide

This guide explains the configuration settings used in the Whole Slide Image (WSI) pipeline, which performs tissue segmentation, patching, and feature extraction.

---

## I/O Settings

-   `wsi_dir`: Path to your folder containing slide images.

-   `wsi_extension`: List of allowed slide file extensions.

    -   Recommended: `.svs`

-   `job_dir`: Directory where output files will be saved.

---

## Segmentation Settings

-   `segmenter`: Segmentation model to use.

    -   Accepted Values: `hest`, `grandqc`
    -   Recommended: `hest`, use `grandqc` if you want fast H&E segmentation

-   `seg_conf_thresh`: Confidence threshold to apply to binarize segmentation predictions. Lower this threhsold to retain more tissue.

    -   Accepted Values: Any number between 0 and 1
    -   Recommended: `0.4` or `0.5` for H&E slides

-   `remove_artifacts`: Whether to run an additional model to remove artifacts.

    -   Accepted Values: `true` or `false`

-   `remove_holes`: Whether to keep holes inside segmented tissue regions.

    -   Accepted Values: `true` or `false`

---

## 🧩 Patching Settings

-   `magnification`: Magnification level for patching and feature extraction. Usually, 20x corresponds to 0.5 micrometers per pixel (mpp).

    -   Accepted Values: `5`, `10`, `20`, `40`, `80`
    -   Recommended: `20` or higher for cell morphology, `5` for overview and identifying tissue structure

-   `patch_size`: Size (in pixels) of square patches at selected magnification level.

    -   Accepted Values: Any integer ≥ 1
    -   Recommended: `224`, `256`, `512`, `1024`

-   `overlap`: Amount of overlap (in pixels) between adjacent patches.

    -   Accepted Values: Any integer ≥ 0 and < `patch_size`
    -   Recommended: `0`

-   `min_tissue_proportion`: [Minimum tissue percentage required to keep a patch.](https://github.com/mahmoodlab/TRIDENT/issues/1)
    -   Accepted Values: Any number between 0 and 1
    -   Recommended: `0`

---

## Feature Extraction Settings

-   `encoder`: Model to use for patch-level feature extraction.

    -   Accepted Values: `conch_v1`, `conch_v15`, `uni_v1`, `uni_v2`, `ctranspath`, `phikon`, `phikon_v2`, `resnet50`
        `gigapath`, `hoptimus0`, `kaiko-vits8`, `kaiko-vits16`, `kaiko-vitb8`, `kaiko-vitb16`, `kaiko-vitl14`, `lunit-vits8`
    -   Recommended: `conch_v1`, `conch_v15`, `uni_v1`, `uni_v2`
    -   For details of each encoder, please refer to the original [TRIDENT](https://github.com/mahmoodlab/TRIDENT/blob/main/README.md#-2-running-trident) repo

-   `batch_size`: Number of patches processed in parallel.
    -   Accepted Values: Any integer ≥ 1
    -   Recommended: `16`, `32`, `64`, `128`, `256`

---

## System Settings

-   `device`: Device to run the pipeline on.
    -   Accepted Values: List of device available at [PyTorch](https://pytorch.org/docs/stable/tensor_attributes.html#torch.device).
    -   Recommended: `cuda`, `cuda:0`, `cpu`, `mps`

---
