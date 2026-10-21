DEFAULTS: dict = {
    "io": {
        "wsi_dir": "/path/to/your/slide/images",
        "job_dir": "./out",
        "process_list": None,
        "wsi_extension": [".svs", ".tif"],
    },
    "segmentation": {
        "segmenter": "hest",
        "seg_conf_thresh": 0.5,
        "remove_artifacts": False,
        "remove_holes": False,
    },
    "patching": {
        "magnification": 20,
        "patch_size": 256,
        "overlap": 0,
        "min_tissue_proportion": 0,
    },
    "features": {
        "encoder": "uni_v2",
        "batch_size": 128,
    },
    "normalization": {
        "enabled": False,
        "method": "macenko",
        "output_dir": "./out/normalized",
        "reference_image": None,
    },
    "system": {
        "device": "cuda",
    },
}
