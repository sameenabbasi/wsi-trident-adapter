# Process List Reference

The adapter accepts CSV manifests that describe which slides to run and any
per-slide overrides. These manifests are used in two places:

- `io.custom_list_of_wsis` inside the YAML config.
- The `--process-list` flag on `wsi-trident-adapter run`.

## CSV schema

The first row must contain a header. The adapter recognises the following
columns:

| Column | Required | Description |
| ------ | -------- | ----------- |
| `wsi` | ✓ | Slide filename (including extension) relative to `io.wsi_dir`. |
| `threshold` | optional | Float in (0, 1). Overrides the default segmentation threshold for the slide. |
| `mpp` | optional | Microns-per-pixel override for patch sampling. |

Additional columns are ignored.

## Minimal example

```csv
wsi
patient001.svs
patient002.svs
```

## With thresholds

```csv
wsi,threshold
patient001.svs,0.55
patient002.svs,0.60
```

## With thresholds and MPP

```csv
wsi,threshold,mpp
patient001.svs,0.55,0.5
patient002.svs,0.60,0.25
```

## Usage tips

- Ensure filenames are unique; duplicates cause the loader to raise an error.
- Avoid empty cells—every populated column must contain a value for each row.
