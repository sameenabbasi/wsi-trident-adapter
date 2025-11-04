# Configuration Reference
Most configuration keys mirror upstream TRIDENT defaults; see the 
[TRIDENT project](https://github.com/mahmoodlab/TRIDENT/tree/main) 
for the canonical reference.

The adapter consumes a YAML configuration file (see `configs/config_template.yaml`)
that mirrors TRIDENT defaults. This document explains every field and offers
practical guidance for tailoring the pipeline to your dataset.

## `io`

| Key | Type | Description |
| --- | ---- | ----------- |
| `wsi_dir` | path | Directory containing input whole-slide images. All files must be directly under this directory. |
| `wsi_extension` | list[str] | File extensions (with dot) considered valid WSIs. The adapter lowercases each extension at runtime. |
| `job_dir` | path | Root directory where output subfolders (one per run) and manifests are created. |
| `custom_list_of_wsis` | path or null | Optional CSV manifest. When provided, the adapter skips autodiscovery and feeds the manifest to TRIDENT. |

Example:

```yaml
io:
  wsi_dir: /data/hospital-a/slides
  wsi_extension: [".svs", ".tif", ".ndpi"]
  job_dir: /output/wsi-trident-out
  custom_list_of_wsis: null
```

### Custom WSI manifests

Set `custom_list_of_wsis` when you want to drive the pipeline with a CSV
manifest. The file format matches the process-list schema described in
[`docs/process-list.md`](process-list.md). If omitted, the adapter discovers
slides automatically by scanning `io.wsi_dir`.

---

## `segmentation`

| Key | Type | Description |
| --- | ---- | ----------- |
| `segmenter` | str | TRIDENT segmenter name (e.g., `hest`, `grandqc`). |
| `seg_conf_thresh` | float | Default confidence threshold used when no per-slide threshold exists. Must lie in (0, 1). |
| `remove_artifacts` | bool | Runs the optional artifact-cleaning pass (read https://www.nature.com/articles/s41467-024-54769-y for details). |
| `remove_holes` | bool | Drop patches that lie above interior holes in the segmentation mask. |

Example:

```yaml
segmentation:
  segmenter: hest
  seg_conf_thresh: 0.5
  remove_artifacts: false
  remove_holes: false
```

## `patching`

| Key | Type | Description |
| --- | ---- | ----------- |
| `magnification` | int | Target magnification used to extract tiles. |
| `patch_size` | int | Tile width/height in pixels. |
| `overlap` | int | Overlap between neighbouring tiles (pixels). |
| `min_tissue_proportion` | float | Minimum tissue fraction required for a tile to be kept. |

Guidance:

- `magnification`: `20` is standard for morphology; `5` for coarse structure.
- `patch_size`: common values are `224`, `256`, `512`, `1024`.
- `overlap`: usually `0`; increase when you need denser coverage.
- `min_tissue_proportion`: between `0` and `1`; start with `0.0`–`0.15`.

Example:

```yaml
patching:
  magnification: 20
  patch_size: 256
  overlap: 0
  min_tissue_proportion: 0
```

## `features`

| Key | Type | Description |
| --- | ---- | ----------- |
| `encoder` | str | Patch encoder registered with TRIDENT (e.g., `uni_v2`, `resnet50`). |
| `batch_size` | int | Tile batch size used during feature extraction. Tune for GPU memory. |

Supported encoders include `conch_v1`, `conch_v15`, `uni_v1`, `uni_v2`,
`ctranspath`, `phikon`, `phikon_v2`, `resnet50`, `gigapath`, `hoptimus0`,
`kaiko-vits8/vits16/vitb8/vitb16/vitl14`, and `lunit-vits8`. Refer to the
[TRIDENT README](https://github.com/mahmoodlab/TRIDENT) for details.

Example:

```yaml
features:
  encoder: resnet50
  batch_size: 64
```

## `system`

| Key | Type | Description |
| --- | ---- | ----------- |
| `device` | str | Runtime device selection, typically `cuda` or `cpu`. |

Common values: `cuda`, `cuda:0`, `cpu`.

Example:

```yaml
system:
  device: cuda
```

## Putting it together

A realistic configuration might look like:

```yaml
io:
  wsi_dir: /path/to/your/slides
  wsi_extension: [".svs", ".tif"]
  job_dir: /path/to/your/outputs
  custom_list_of_wsis: null

segmentation:
  segmenter: hest
  seg_conf_thresh: 0.5
  remove_artifacts: false
  remove_holes: false

patching:
  magnification: 20
  patch_size: 256
  overlap: 0
  min_tissue_proportion: 0

features:
  encoder: uni_v2
  batch_size: 128

system:
  device: cuda
```

Use this reference alongside the CLI (`wsi-trident-adapter config`) to generate
a baseline file, then edit the fields described above to match your workload.
