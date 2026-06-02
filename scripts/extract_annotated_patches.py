#!/usr/bin/env python
"""
Tile WSIs and produce paired raw-patch / binary-mask images from GeoJSON
blood-vessel annotations.

For every tile extracted from a slide the script writes two files:
  patches/<slide>/tile_NNNN_raw.png   — RGB patch at the target magnification
  masks/<slide>/tile_NNNN_mask.png    — binary mask (0 = background, 1 = vessel)

The mask is produced by rasterising the GeoJSON polygons (filled) that overlap
each patch.  Polygon outlines without a fill are treated as filled regions.

GeoJSON coordinate assumption
  Coordinates are in full-resolution (level-0) pixel space, i.e. the default
  QuPath export format.  Pass --geojson_mpp and --slide_mpp to scale
  physical-unit annotations to pixel space.

Usage
-----
python extract_annotated_patches.py \\
    --wsi_dir   /data/svs \\
    --annot_dir /data/geojsons \\
    --out_dir   /data/output \\
    [--magnification 20] [--patch_size 256] [--overlap 0] \\
    [--filter_background] [--bg_thresh 0.85] \\
    [--num_workers 4]

Slides without a matching .geojson file are skipped.
Matching is by stem name: slide_A.svs ↔ slide_A.geojson
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import box as shapely_box
from shapely.geometry import shape
from tqdm import tqdm


# ---------------------------------------------------------------------------
# GeoJSON loading
# ---------------------------------------------------------------------------

def load_annotation_polygons(geojson_path: Path, scale: float = 1.0) -> list:
    """
    Return a list of Shapely geometries from a GeoJSON file.

    scale: multiply all coordinates by this factor to convert from the
           annotation coordinate space to level-0 pixel space.
    """
    with open(geojson_path) as fh:
        data = json.load(fh)

    gtype = data.get("type", "")
    if gtype == "FeatureCollection":
        features = data.get("features", [])
    elif gtype == "Feature":
        features = [data]
    elif gtype in ("Polygon", "MultiPolygon", "GeometryCollection"):
        features = [{"geometry": data}]
    else:
        features = data.get("features", [])

    polygons = []
    for feat in features:
        geom = feat.get("geometry")
        if geom:
            polygons.append(shape(geom))

    if scale != 1.0:
        import shapely.affinity as saff
        polygons = [saff.scale(p, xfact=scale, yfact=scale, origin=(0, 0)) for p in polygons]

    return polygons


# ---------------------------------------------------------------------------
# Tiling helpers
# ---------------------------------------------------------------------------

def iter_tile_coords(
    slide_width: int,
    slide_height: int,
    patch_size_l0: int,
    stride_l0: int,
) -> list[tuple[int, int]]:
    """Return all (x, y) top-left coordinates for a full-coverage tiling."""
    coords = []
    x = 0
    while x + patch_size_l0 <= slide_width:
        y = 0
        while y + patch_size_l0 <= slide_height:
            coords.append((x, y))
            y += stride_l0
        # include a partial row at the bottom edge
        if y - stride_l0 + patch_size_l0 < slide_height:
            coords.append((x, slide_height - patch_size_l0))
        x += stride_l0
    # include a partial column at the right edge
    if x - stride_l0 + patch_size_l0 < slide_width:
        x = slide_width - patch_size_l0
        y = 0
        while y + patch_size_l0 <= slide_height:
            coords.append((x, y))
            y += stride_l0
        if y - stride_l0 + patch_size_l0 < slide_height:
            coords.append((x, slide_height - patch_size_l0))

    # deduplicate while preserving order
    seen: set[tuple[int, int]] = set()
    unique = []
    for c in coords:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def is_background(patch_rgb: np.ndarray, thresh: float) -> bool:
    """True if more than `thresh` fraction of pixels are near-white."""
    white_mask = np.all(patch_rgb > 220, axis=-1)
    return white_mask.mean() > thresh


# ---------------------------------------------------------------------------
# Mask rasterisation
# ---------------------------------------------------------------------------

def rasterise_mask(
    x: int,
    y: int,
    patch_size: int,
    level_downsample: float,
    polygons: list,
) -> Image.Image:
    """
    Build a (patch_size × patch_size) binary mask image (mode "L", values 0/1).

    x, y              top-left corner of the patch in level-0 pixel space
    level_downsample  pixels-at-level-0 per pixel-at-target-level
    polygons          Shapely geometries in level-0 pixel coordinates
    """
    patch_size_l0 = patch_size * level_downsample
    patch_box = shapely_box(x, y, x + patch_size_l0, y + patch_size_l0)

    mask = Image.new("L", (patch_size, patch_size), 0)
    draw = ImageDraw.Draw(mask)

    for poly in polygons:
        if not poly.intersects(patch_box):
            continue

        # Handle both Polygon and MultiPolygon
        if poly.geom_type == "MultiPolygon":
            sub_polys = list(poly.geoms)
        elif poly.geom_type == "Polygon":
            sub_polys = [poly]
        else:
            continue

        for sub in sub_polys:
            # Exterior ring → fill with 1
            ext_px = [
                ((cx - x) / level_downsample, (cy - y) / level_downsample)
                for cx, cy in sub.exterior.coords
            ]
            if len(ext_px) >= 3:
                draw.polygon(ext_px, fill=1)

            # Interior rings (holes) → erase back to 0
            for interior in sub.interiors:
                int_px = [
                    ((cx - x) / level_downsample, (cy - y) / level_downsample)
                    for cx, cy in interior.coords
                ]
                if len(int_px) >= 3:
                    draw.polygon(int_px, fill=0)

    return mask


# ---------------------------------------------------------------------------
# Per-slide processing
# ---------------------------------------------------------------------------

def _process_tile(args_tuple) -> bool:
    """Worker function for parallel tile extraction.  Returns True if saved."""
    (
        slide_path,
        x, y,
        tile_idx,
        patch_size,
        patch_level,
        level_downsample,
        polygons,
        raw_dir,
        mask_dir,
        filter_bg,
        bg_thresh,
    ) = args_tuple

    import openslide

    slide = openslide.OpenSlide(str(slide_path))
    patch_img = slide.read_region((x, y), patch_level, (patch_size, patch_size)).convert("RGB")
    slide.close()

    if filter_bg:
        arr = np.asarray(patch_img)
        if is_background(arr, bg_thresh):
            return False

    name = f"tile_{tile_idx:04d}"
    patch_img.save(raw_dir / f"{name}_raw.png")

    mask_img = rasterise_mask(x, y, patch_size, level_downsample, polygons)
    mask_img.save(mask_dir / f"{name}_mask.png")

    return True


def process_slide(
    slide_path: Path,
    geojson_path: Path,
    out_dir: Path,
    args: argparse.Namespace,
    coord_scale: float = 1.0,
) -> dict:
    import openslide

    slide_name = slide_path.stem
    raw_dir = out_dir / "patches" / slide_name
    mask_dir = out_dir / "masks" / slide_name
    raw_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    slide = openslide.OpenSlide(str(slide_path))
    W, H = slide.dimensions  # level-0 size

    scan_mag = float(
        slide.properties.get(
            openslide.PROPERTY_NAME_OBJECTIVE_POWER,
            slide.properties.get("tiff.XResolution", 40),
        )
    )
    target_downsample = scan_mag / args.magnification
    patch_level = slide.get_best_level_for_downsample(target_downsample)
    level_downsample = slide.level_downsamples[patch_level]
    slide.close()

    patch_size_l0 = int(args.patch_size * level_downsample)
    stride_l0 = int((args.patch_size - args.overlap) * level_downsample)

    polygons = load_annotation_polygons(geojson_path, scale=coord_scale)

    coords = iter_tile_coords(W, H, patch_size_l0, stride_l0)

    work_items = [
        (
            slide_path,
            x, y,
            idx,
            args.patch_size,
            patch_level,
            level_downsample,
            polygons,
            raw_dir,
            mask_dir,
            args.filter_background,
            args.bg_thresh,
        )
        for idx, (x, y) in enumerate(coords)
    ]

    saved = 0
    skipped = 0

    with ThreadPoolExecutor(max_workers=args.num_workers) as pool:
        futures = {pool.submit(_process_tile, item): item for item in work_items}
        for future in tqdm(
            as_completed(futures),
            total=len(work_items),
            desc=f"  {slide_name}",
            unit="tile",
            leave=False,
        ):
            result = future.result()
            if result:
                saved += 1
            else:
                skipped += 1

    # Sequential rename so tile indices match saved order (no gaps from skipped)
    # Re-number tiles after filtering to produce a contiguous index
    if args.filter_background and skipped > 0:
        _renumber_tiles(raw_dir, mask_dir)
        saved = len(list(raw_dir.glob("*_raw.png")))

    return {"saved": saved, "skipped": skipped}


def _renumber_tiles(raw_dir: Path, mask_dir: Path) -> None:
    """Re-number tile files so the index is contiguous after background filtering."""
    raw_files = sorted(raw_dir.glob("*_raw.png"), key=lambda p: int(p.stem.split("_")[1]))
    for new_idx, raw_path in enumerate(raw_files):
        old_idx_str = raw_path.stem.split("_")[1]
        new_name = f"tile_{new_idx:04d}"
        old_name = f"tile_{old_idx_str}"

        new_raw = raw_dir / f"{new_name}_raw.png"
        new_mask = mask_dir / f"{new_name}_mask.png"

        if raw_path != new_raw:
            raw_path.rename(new_raw)
            old_mask = mask_dir / f"{old_name}_mask.png"
            if old_mask.exists():
                old_mask.rename(new_mask)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required
    p.add_argument("--wsi_dir", type=Path, required=True,
                   help="Directory containing WSI files (.svs, .tif, etc.).")
    p.add_argument("--annot_dir", type=Path, required=True,
                   help="Directory containing .geojson annotation files (matched by stem).")
    p.add_argument("--out_dir", type=Path, required=True,
                   help="Root output directory.")

    # Tiling
    p.add_argument("--magnification", type=int, default=20,
                   help="Target extraction magnification (default: 20).")
    p.add_argument("--patch_size", type=int, default=256,
                   help="Patch size in pixels at target magnification (default: 256).")
    p.add_argument("--overlap", type=int, default=0,
                   help="Overlap in pixels between adjacent tiles (default: 0).")

    # Background filtering
    p.add_argument("--filter_background", action="store_true",
                   help="Skip tiles that are mostly white/background.")
    p.add_argument("--bg_thresh", type=float, default=0.85,
                   help="Fraction of near-white pixels above which a tile is considered "
                        "background (default: 0.85). Only used with --filter_background.")

    # Coordinate scaling (if GeoJSON uses physical units instead of pixels)
    p.add_argument("--coord_scale", type=float, default=1.0,
                   help="Multiply GeoJSON coordinates by this factor to convert to "
                        "level-0 pixel space (default: 1.0 = pixel coords).")

    # Performance
    p.add_argument("--num_workers", type=int,
                   default=min(8, mp.cpu_count()),
                   help="Number of parallel tile-extraction threads per slide.")

    return p.parse_args()


def main() -> None:
    args = parse_args()

    wsi_dir = args.wsi_dir.resolve()
    annot_dir = args.annot_dir.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Discover slides with matching GeoJSON
    wsi_extensions = {".svs", ".tif", ".tiff", ".ndpi", ".scn", ".mrxs"}
    slide_map = {
        p.stem: p
        for p in wsi_dir.iterdir()
        if p.is_file() and p.suffix.lower() in wsi_extensions
    }
    geojson_map = {
        p.stem: p
        for p in annot_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".geojson"
    }

    matched = {
        stem: (slide_map[stem], geojson_map[stem])
        for stem in slide_map
        if stem in geojson_map
    }

    if not matched:
        sys.exit(
            "[error] No slides with matching GeoJSON annotations found.\n"
            f"  WSI dir:   {wsi_dir}\n"
            f"  Annot dir: {annot_dir}\n"
            "  Filenames must match by stem: slide_A.svs ↔ slide_A.geojson"
        )

    unmatched = set(slide_map) - set(matched)
    print(f"Found {len(matched)} slide(s) with annotations"
          + (f"  ({len(unmatched)} slide(s) skipped — no GeoJSON)" if unmatched else ""))
    print(f"Output: {out_dir}")
    print()

    totals = {"saved": 0, "skipped": 0}
    for stem, (slide_path, geojson_path) in matched.items():
        print(f"Slide: {slide_path.name}")
        result = process_slide(
            slide_path,
            geojson_path,
            out_dir,
            args,
            coord_scale=args.coord_scale,
        )
        totals["saved"] += result["saved"]
        totals["skipped"] += result["skipped"]
        print(f"  saved={result['saved']}  skipped={result['skipped']}")

    print()
    print(f"Done.  Total tiles saved: {totals['saved']}  skipped: {totals['skipped']}")
    print(f"  patches/  →  {out_dir / 'patches'}")
    print(f"  masks/    →  {out_dir / 'masks'}")


if __name__ == "__main__":
    main()
