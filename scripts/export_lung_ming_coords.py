#!/usr/bin/env python
"""
Turn TRIDENT coordinate .h5 files into plain CSVs, and optionally materialise
the patch images themselves.

TRIDENT's patching stage writes one <slide>_patches.h5 per slide containing a
`coords` dataset (top-left corners in level-0 pixel space) plus attributes
describing the patch geometry.  That file is the authoritative record of which
tissue regions survived background removal; this script re-expresses it as

    coords_csv/<slide>.csv        tile_id, x, y   (level-0 top-left corners)
    coords_csv/<slide>_meta.json  patch size, level, downsample, magnification

and, with --save_patches, also

    patches_png/<slide>/tile_NNNN_x{X}_y{Y}.png

Coordinate convention matches extract_annotated_patches.py: x/y are the
top-left corner in level-0 pixels; multiply patch_size by `downsample` to get
the level-0 extent of a patch.

Usage
-----
python export_lung_ming_coords.py \\
    --coords_dir /cluster/projects/kumargroup/lung_ming/processed/20x_256px_0px_overlap/patches \\
    --out_dir    /cluster/projects/kumargroup/lung_ming/processed \\
    [--wsi_dir /cluster/projects/kumargroup/lung-data-ming --save_patches] \\
    [--num_workers 8]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import h5py
import numpy as np


def _attr(attrs, *names, default=None):
    """First present attribute among `names`, decoded to a python scalar."""
    for name in names:
        if name in attrs:
            value = attrs[name]
            if isinstance(value, bytes):
                return value.decode()
            if isinstance(value, np.generic):
                return value.item()
            return value
    return default


def read_coords(h5_path: Path):
    """Return (coords array of shape (N, 2), metadata dict)."""
    with h5py.File(h5_path, "r") as f:
        if "coords" not in f:
            raise ValueError(f"{h5_path.name}: no 'coords' dataset")
        dset = f["coords"]
        coords = dset[:]

        # TRIDENT has moved these between the dataset and the file root across
        # versions, so check both.
        attrs = dict(f.attrs)
        attrs.update(dict(dset.attrs))

        patch_size = _attr(attrs, "patch_size")
        meta = {
            "source_h5": str(h5_path),
            "n_patches": int(coords.shape[0]),
            "patch_size": patch_size,
            "patch_size_level0": _attr(attrs, "patch_size_level0"),
            "patch_level": _attr(attrs, "level", "patch_level"),
            "downsample": _attr(attrs, "downsample", "factor"),
            "target_magnification": _attr(
                attrs, "target_magnification", "target_mag"
            ),
            "coord_space": "level-0 pixels, top-left corner",
        }

    if coords.ndim != 2 or coords.shape[1] != 2:
        raise ValueError(f"{h5_path.name}: unexpected coords shape {coords.shape}")

    return coords, meta


def dump_patch_images(slide_path: Path, coords, meta, out_dir: Path) -> int:
    import openslide

    slide = openslide.OpenSlide(str(slide_path))
    level = int(meta["patch_level"] or 0)
    patch_size = int(meta["patch_size"])

    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, (x, y) in enumerate(coords):
        x, y = int(x), int(y)
        patch = slide.read_region((x, y), level, (patch_size, patch_size))
        patch.convert("RGB").save(out_dir / f"tile_{idx:05d}_x{x}_y{y}.png")

    slide.close()
    return len(coords)


def process_slide(h5_path: Path, args) -> tuple[str, int, str | None]:
    stem = h5_path.name
    for suffix in ("_patches.h5", ".h5"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break

    try:
        coords, meta = read_coords(h5_path)
    except Exception as exc:  # noqa: BLE001 - one bad slide must not kill the run
        return stem, 0, str(exc)

    csv_dir = Path(args.out_dir) / "coords_csv"
    csv_dir.mkdir(parents=True, exist_ok=True)

    with open(csv_dir / f"{stem}.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["tile_id", "x", "y"])
        for idx, (x, y) in enumerate(coords):
            writer.writerow([idx, int(x), int(y)])

    meta["slide"] = stem
    with open(csv_dir / f"{stem}_meta.json", "w") as fh:
        json.dump(meta, fh, indent=2)

    if args.save_patches:
        if meta["patch_size"] is None:
            return stem, len(coords), "patch_size missing from h5; skipped images"
        slide_path = Path(args.wsi_dir) / f"{stem}.svs"
        if not slide_path.exists():
            return stem, len(coords), f"slide not found: {slide_path.name}"
        try:
            dump_patch_images(
                slide_path, coords, meta, Path(args.out_dir) / "patches_png" / stem
            )
        except Exception as exc:  # noqa: BLE001
            return stem, len(coords), f"image dump failed: {exc}"

    return stem, len(coords), None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--coords_dir", required=True,
                        help="Directory of TRIDENT <slide>_patches.h5 files.")
    parser.add_argument("--out_dir", required=True,
                        help="Where coords_csv/ (and patches_png/) are written.")
    parser.add_argument("--wsi_dir",
                        help="Slide directory; required with --save_patches.")
    parser.add_argument("--save_patches", action="store_true",
                        help="Also write each patch as a PNG (slow, large).")
    parser.add_argument("--num_workers", type=int, default=4)
    args = parser.parse_args()

    if args.save_patches and not args.wsi_dir:
        parser.error("--save_patches requires --wsi_dir")

    h5_files = sorted(Path(args.coords_dir).glob("*.h5"))
    if not h5_files:
        print(f"[ERROR] No .h5 files under {args.coords_dir}", file=sys.stderr)
        return 1

    print(f"[INFO] {len(h5_files)} coordinate files found")

    total_patches = 0
    failures = []
    with ProcessPoolExecutor(max_workers=args.num_workers) as pool:
        futures = {pool.submit(process_slide, p, args): p for p in h5_files}
        for future in as_completed(futures):
            stem, n, error = future.result()
            total_patches += n
            if error:
                failures.append((stem, error))
                print(f"  [WARN] {stem}: {error}")
            else:
                print(f"  {stem}: {n} patches")

    print(f"\n[INFO] Total patches: {total_patches}")
    if failures:
        print(f"[INFO] {len(failures)} slide(s) had problems:")
        for stem, error in failures:
            print(f"  {stem}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
