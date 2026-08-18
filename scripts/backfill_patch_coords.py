#!/usr/bin/env python
"""
Recover level-0 coordinates for patches that were already extracted.

`extract_annotated_patches.py` tiles a slide on a deterministic grid and
assigns tile indices by position in that grid, so for a run that did NOT use
--filter_background the index alone pins the coordinate: tile_NNNN is
coords[NNNN].  This script rebuilds the grid from the slide metadata (no pixel
reads) and writes the coords.csv / coords_meta.json that the extractor now
emits into <out_dir>/coords/.  Patch files are left untouched unless --rename
is passed; the CSV maps the existing tile numbers to their coordinates either
way.

The tiling parameters must match the original extraction run.  The defaults
here match scripts/extract_patches_masks.sh (20x, 256 px, no overlap).

Usage
-----
python backfill_patch_coords.py \\
    --wsi_dir /cluster/projects/kumargroup/ch-fibrosis \\
    --out_dir /cluster/projects/kumargroup/ch_fibrosis_analysis/trident \\
    [--magnification 20] [--patch_size 256] [--overlap 0] \\
    [--rename] [--dry_run]

A slide is skipped with a loud warning if its tile count does not match the
reconstructed grid, since that means the index no longer maps to the grid
(e.g. the run used --filter_background, or files were deleted).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract_annotated_patches import (  # noqa: E402
    COORD_DIR_NAME,
    iter_tile_coords,
    parse_tile_name,
    tile_name,
    write_coord_files,
)

SLIDE_EXTS = {".svs", ".tif", ".tiff", ".ndpi", ".scn", ".mrxs", ".vms", ".bif"}


def existing_tiles(raw_dir: Path) -> list[tuple[int, Path]]:
    """Return (tile_idx, raw_path) for every patch, ordered by index.

    Handles both the old `tile_NNNN_raw.png` layout and the new
    `tile_NNNN_xX_yY_raw.png` layout.
    """
    tiles = []
    for raw_path in raw_dir.glob("*_raw.png"):
        stem = raw_path.stem[: -len("_raw")]
        parsed = parse_tile_name(stem)
        if parsed is not None:
            tiles.append((parsed[0], raw_path))
            continue
        parts = stem.split("_")
        if len(parts) == 2 and parts[0] == "tile" and parts[1].isdigit():
            tiles.append((int(parts[1]), raw_path))
        else:
            print(f"    [warn] unrecognised tile filename, ignored: {raw_path.name}")
    tiles.sort()
    return tiles


def _import_openslide():
    """Import openslide with an actionable message if the native lib is missing."""
    try:
        import openslide
    except (ImportError, ModuleNotFoundError) as exc:
        sys.exit(
            f"[error] could not load OpenSlide: {exc}\n"
            "        Run this in the same conda env used for extraction: the grid\n"
            "        depends on the OpenSlide level metadata, so it must match the\n"
            "        env that produced the patches.\n"
            "            source ~/miniforge3/bin/activate\n"
            "            conda activate <env>      # `conda info --envs` lists them\n"
            "        If OpenSlide is missing there too: pip install openslide-bin"
        )
    return openslide


def slide_grid(slide_path: Path, args: argparse.Namespace) -> tuple[list, dict]:
    """Rebuild the extraction grid for one slide.  Reads metadata only."""
    openslide = _import_openslide()

    slide = openslide.OpenSlide(str(slide_path))
    W, H = slide.dimensions

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

    coords = iter_tile_coords(W, H, patch_size_l0, stride_l0)
    meta = {
        "slide": slide_path.stem,
        "slide_path": str(slide_path),
        "slide_width": W,
        "slide_height": H,
        "scan_magnification": scan_mag,
        "target_magnification": args.magnification,
        "patch_level": patch_level,
        "downsample": level_downsample,
        "patch_size": args.patch_size,
        "patch_size_level0": patch_size_l0,
        "overlap": args.overlap,
        "stride_level0": stride_l0,
        "coord_space": "level-0 pixels, top-left corner",
        "source": "backfilled by backfill_patch_coords.py",
    }
    return coords, meta


def process_slide_dir(
    raw_dir: Path,
    mask_dir: Path,
    slide_path: Path,
    coord_dir: Path,
    args: argparse.Namespace,
) -> str:
    tiles = existing_tiles(raw_dir)
    if not tiles:
        return "empty"

    coords, meta = slide_grid(slide_path, args)

    if len(tiles) != len(coords):
        print(
            f"    [SKIP] tile count {len(tiles)} != reconstructed grid "
            f"{len(coords)}.  Indices cannot be trusted for this slide."
        )
        return "mismatch"

    indices = [idx for idx, _ in tiles]
    if indices != list(range(len(coords))):
        print("    [SKIP] tile indices are not contiguous 0..N-1.")
        return "mismatch"

    saved_tiles = [(idx, coords[idx][0], coords[idx][1]) for idx, _ in tiles]
    meta["tiles_saved"] = len(saved_tiles)
    meta["tiles_skipped"] = 0

    stems = [raw_path.stem[: -len("_raw")] for _, raw_path in tiles]

    renamed = 0
    if args.rename:
        for i, ((idx, x, y), old_stem) in enumerate(zip(saved_tiles, stems)):
            new_name = tile_name(idx, x, y)
            if old_stem == new_name:
                continue
            renamed += 1
            if args.dry_run:
                continue
            (raw_dir / f"{old_stem}_raw.png").rename(raw_dir / f"{new_name}_raw.png")
            old_mask = mask_dir / f"{old_stem}_mask.png"
            if old_mask.exists():
                old_mask.rename(mask_dir / f"{new_name}_mask.png")
            else:
                print(f"    [warn] no mask for {old_stem}")
            stems[i] = new_name

    # The CSV always names the files as they actually sit on disk, so it stays
    # correct whether or not --rename was used.
    missing = [s for s in stems if not (mask_dir / f"{s}_mask.png").exists()]
    if missing:
        print(f"    [warn] {len(missing)} patches have no matching mask")

    if args.dry_run:
        print(f"    [dry-run] would write {coord_dir}/{raw_dir.name}.csv "
              f"for {len(saved_tiles)} tiles"
              + (f", rename {renamed} files" if args.rename else " (no renaming)"))
        return "ok"

    write_coord_files(coord_dir, raw_dir.name, saved_tiles, meta, stems=stems)
    print(f"    wrote coords for {len(saved_tiles)} tiles"
          + (f", renamed {renamed} files" if args.rename else " (files untouched)"))
    return "ok"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--wsi_dir", type=Path, required=True,
                   help="Directory holding the original slides.")
    p.add_argument("--out_dir", type=Path, required=True,
                   help="Extraction output dir (containing patches/ and masks/).")
    p.add_argument("--magnification", type=float, default=20)
    p.add_argument("--patch_size", type=int, default=256)
    p.add_argument("--overlap", type=int, default=0)
    p.add_argument("--rename", action="store_true",
                   help="Also rename tiles to tile_NNNN_xX_yY_{raw,mask}.png. "
                        "Off by default: patch files are left untouched and only "
                        "coords.csv / coords_meta.json are written.")
    p.add_argument("--dry_run", action="store_true",
                   help="Report what would happen without touching any file.")
    args = p.parse_args()

    _import_openslide()

    patches_root = args.out_dir / "patches"
    masks_root = args.out_dir / "masks"
    coord_dir = args.out_dir / COORD_DIR_NAME
    if not patches_root.is_dir():
        sys.exit(f"[error] patches directory not found: {patches_root}")

    slide_map = {
        sp.stem: sp
        for sp in sorted(args.wsi_dir.iterdir())
        if sp.is_file() and sp.suffix.lower() in SLIDE_EXTS
    }

    counts = {"ok": 0, "mismatch": 0, "empty": 0, "no_slide": 0}
    for raw_dir in sorted(d for d in patches_root.iterdir() if d.is_dir()):
        slide_name = raw_dir.name
        print(f"[slide] {slide_name}")
        slide_path = slide_map.get(slide_name)
        if slide_path is None:
            print(f"    [SKIP] no matching slide in {args.wsi_dir}")
            counts["no_slide"] += 1
            continue
        counts[
            process_slide_dir(
                raw_dir, masks_root / slide_name, slide_path, coord_dir, args
            )
        ] += 1

    print("\n" + "=" * 60)
    print(f"Done.  ok={counts['ok']}  mismatch={counts['mismatch']}  "
          f"empty={counts['empty']}  no_slide={counts['no_slide']}")
    if counts["mismatch"]:
        print("Slides marked mismatch must be re-extracted to get coordinates.")


if __name__ == "__main__":
    main()
