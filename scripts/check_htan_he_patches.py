#!/usr/bin/env python3
"""Audit which HTAN H&E slides actually have patch coordinates.

    python scripts/check_htan_he_patches.py            # summary + problems
    python scripts/check_htan_he_patches.py --all      # every slide, one per line
    python scripts/check_htan_he_patches.py --stage feat

Cross-references the H&E slides on disk (selected from the manifest the same
way prepare_htan_he_lists.py selects them) against the coords h5 files TRIDENT
wrote, so "did everything patch?" is answered from the outputs rather than from
a job's exit status -- the pipeline runs with skip_errors=True, so an array task
can exit 0 having skipped slides it could not open.

Slides parked in needs_mpp.csv are reported separately: they are expected to be
missing and should not read as failures.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
from pathlib import Path

# Reuse the manifest selection so the two scripts can never disagree on what
# counts as an H&E slide.
_spec = importlib.util.spec_from_file_location(
    "_prep", Path(__file__).with_name("prepare_htan_he_lists.py")
)
_prep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_prep)


def patch_count(h5_path: Path) -> int | None:
    """Number of coordinates in a TRIDENT patches h5, or None if unreadable."""
    try:
        import h5py
    except ModuleNotFoundError:
        return None
    try:
        with h5py.File(h5_path, "r") as f:
            if "coords" not in f:
                return None
            return int(f["coords"].shape[0])
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=("coords", "feat"), default="coords")
    ap.add_argument("--data-dir", type=Path, default=_prep.DATA_DIR)
    ap.add_argument("--manifest", type=Path, default=_prep.MANIFEST)
    ap.add_argument("--out-dir", type=Path, default=_prep.OUT_DIR)
    ap.add_argument("--all", action="store_true", help="List every slide, not just problems.")
    ap.add_argument("--by-atlas", action="store_true",
                    help="Break the summary down by atlas + modality.")
    args = ap.parse_args()

    if args.stage == "coords":
        done_dir = args.out_dir / _prep.COORDS_SUBDIR / "patches"
        suffix = "_patches.h5"
    else:
        done_dir = args.out_dir / _prep.COORDS_SUBDIR / f"features_{_prep.ENCODER}"
        suffix = ".h5"

    he_rows = _prep.he_basenames_from_manifest(args.manifest)
    on_disk = sorted(
        p.name for p in args.data_dir.iterdir()
        if p.is_file() and not p.name.startswith("._")
        and p.suffix.lower() in _prep.SLIDE_EXTS and p.name in he_rows
    )

    parked = set()
    nm = args.out_dir / "process_lists" / "needs_mpp.csv"
    if nm.is_file():
        with nm.open(newline="") as fh:
            parked = {r["wsi"].strip() for r in csv.DictReader(fh) if r.get("wsi")}

    ok, empty, missing, locked = [], [], [], []
    total_patches = 0

    for name in on_disk:
        h5 = done_dir / f"{Path(name).stem}{suffix}"
        if (done_dir / f"{h5.name}.lock").exists():
            locked.append(name)
        elif not h5.is_file():
            missing.append(name)
        elif h5.stat().st_size == 0:
            empty.append(name)
        else:
            n = patch_count(h5)
            ok.append((name, n))
            total_patches += n or 0
            if args.all:
                print(f"  OK      {name:55s} {'' if n is None else f'{n:>8,} patches'}")

    missing_unexpected = [n for n in missing if n not in parked]
    missing_parked = [n for n in missing if n in parked]

    if args.by_atlas:
        # A cohort is only as done as its worst group; a single total hides a
        # whole modality sitting at zero.
        groups: dict[tuple[str, str], dict[str, int]] = {}
        done = {n for n, _ in ok}
        for name in on_disk:
            row = he_rows[name]
            key = (row.get("atlas", "?"), row.get("modality", "?"))
            g = groups.setdefault(key, {"n": 0, "ok": 0, "parked": 0, "missing": 0})
            g["n"] += 1
            if name in done:
                g["ok"] += 1
            elif name in parked:
                g["parked"] += 1
            else:
                g["missing"] += 1

        print("")
        print(f"{'atlas':20s} {'modality':16s} {'on disk':>8s} {'patched':>8s}"
              f" {'parked':>8s} {'missing':>8s}")
        for (atlas, modality), g in sorted(groups.items()):
            print(f"{atlas:20s} {modality:16s} {g['n']:>8d} {g['ok']:>8d}"
                  f" {g['parked']:>8d} {g['missing']:>8d}")

    print("")
    print(f"[INFO] Stage                  : {args.stage}")
    print(f"[INFO] Coords dir             : {done_dir}")
    print(f"[INFO] H&E slides on disk     : {len(on_disk)}")
    print(f"[INFO]   with output          : {len(ok)}"
          + (f"  ({total_patches:,} patches)" if total_patches else ""))
    print(f"[INFO]   parked (no mpp)      : {len(missing_parked)}")
    print(f"[WARN]   MISSING              : {len(missing_unexpected)}")
    print(f"[WARN]   empty file           : {len(empty)}")
    print(f"[WARN]   still locked         : {len(locked)}")

    for label, group in (("MISSING", missing_unexpected), ("EMPTY", empty),
                         ("LOCKED", locked)):
        for name in group:
            print(f"[WARN] {label:8s} {name}")

    if any((missing_unexpected, empty, locked)):
        print("")
        print("[INFO] Re-run the stage to retry these; the prepare script skips"
              " whatever already succeeded.")
        return 1

    zero = [n for n, c in ok if c == 0]
    if zero:
        print("")
        print(f"[WARN] {len(zero)} slide(s) produced an h5 with ZERO patches"
              " -- segmentation likely found no tissue:")
        for name in zero:
            print(f"[WARN]   {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
