#!/usr/bin/env python3
"""Build process-list chunks for the H&E slides of the HTAN spatial-proteomics cohort.

Run on the LOGIN NODE before submitting the array job:

    python scripts/prepare_htan_he_lists.py            # coords stage (default)
    python scripts/prepare_htan_he_lists.py --stage feat

The cohort pairs each spatial-proteomics image with an H&E scan of the same
section.  Which file is which is *not* recoverable from the filename alone
(``S026.ome.tif`` is H&E, ``S026TL.ome.tiff`` is the CODEX partner), so slide
selection is driven by the manifest: rows with ``role == histology`` are the
H&E scans, ``role == spatial`` are their multiplexed partners.  The download
directory is flat while the manifest stores atlas-relative paths, so matching
is done on basenames (verified unique across the manifest).

Microns-per-pixel is read from each file's own metadata.  OpenSlide does not
parse OME-XML and generally reports nothing useful for .qptiff, so TRIDENT
would otherwise guess the magnification; every slide therefore carries an
explicit ``mpp`` column.  ``--dims-tsv`` takes the H&E pixel size from a
pre-computed dimensions report instead (joined to the manifest on the
``biospecimen`` column) and warns when it disagrees with the file's own
metadata.  Precedence: --extra-mpp > --dims-tsv > file metadata > --default-mpp.  Slides whose metadata yields no pixel size are held
back into ``needs_mpp.csv`` rather than silently defaulted -- fill that file in
and re-run with --extra-mpp, or pass --default-mpp to accept one value for all
of them.

Outputs (under OUT_DIR):
    process_lists/chunk_<i>.csv        wsi,mpp      (coords stage)
    process_lists_feat/chunk_<i>.csv   wsi,mpp      (feat stage)
    process_lists/needs_mpp.csv        slides skipped for want of a pixel size
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


# tifffile is needed only to probe pixel size out of a file's own metadata.
# Login nodes often have a bare python, and when --dims-tsv/--extra-mpp/
# --default-mpp already supply every mpp there is nothing to probe, so the
# import is deferred rather than made a hard requirement of the script.
try:
    import tifffile
except ModuleNotFoundError:  # pragma: no cover - environment-dependent
    tifffile = None

# ---- EDIT THESE ----
DATA_DIR = Path("/cluster/projects/kumargroup/sean/data/HTAN_SPATIAL_PROTEOMICS")
MANIFEST = Path("/cluster/home/t140585uhn/manifest_same_section_all.tsv")
OUT_DIR = Path("/cluster/projects/kumargroup/sean/data/HTAN_SPATIAL_PROTEOMICS/processed")
N_WORKERS = 4
# --------------------

ENCODER = "uni_v2"
COORDS_SUBDIR = "20x_256px_0px_overlap"
# .ome.tif/.ome.tiff are matched on their final suffix, the way the adapter's
# slide lister does; .qptiff must be listed explicitly in the job config too.
SLIDE_EXTS = (".svs", ".tif", ".tiff", ".qptiff")


def he_basenames_from_manifest(manifest: Path) -> dict[str, dict[str, str]]:
    """Return {basename: manifest row} for every ``role == histology`` row."""
    rows: dict[str, dict[str, str]] = {}
    with manifest.open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            if row.get("role") != "histology":
                continue
            name = row["filename"].rsplit("/", 1)[-1].strip()
            if name in rows:
                raise SystemExit(
                    f"[ERROR] Duplicate H&E basename in manifest: {name!r}. "
                    "Basename matching against the flat download directory is "
                    "no longer safe."
                )
            rows[name] = row
    return rows


def mpp_from_file(path: Path) -> tuple[float | None, str]:
    """Microns-per-pixel at full resolution, from OME-XML or TIFF resolution tags."""
    if tifffile is None:
        raise ModuleNotFoundError(
            "tifffile is not installed in this python; activate the conda env "
            "(conda activate methylcdm_h100) or supply mpp via --dims-tsv / "
            "--extra-mpp / --default-mpp"
        )
    with tifffile.TiffFile(path) as tf:
        # 1) OME-XML PhysicalSizeX
        ome = tf.ome_metadata
        if ome:
            m = re.search(r'PhysicalSizeX="([\d.eE+-]+)"', ome)
            u = re.search(r'PhysicalSizeXUnit="([^"]+)"', ome)
            if m:
                val = float(m.group(1))
                unit = u.group(1) if u else "µm"
                if unit == "nm":
                    val /= 1000.0
                elif unit == "mm":
                    val *= 1000.0
                return val, f"OME PhysicalSizeX ({unit})"

        # 2) Aperio .svs stashes MPP in the page description
        desc = tf.pages[0].description or ""
        if "Aperio" in desc or "MPP" in desc:
            m = re.search(r"\bMPP\s*=\s*([\d.eE+-]+)", desc)
            if m:
                return float(m.group(1)), "Aperio MPP"

        # 3) TIFF resolution tags (Akoya .qptiff, plain TIFF)
        page = tf.pages[0]
        xres = page.tags.get("XResolution")
        runit = page.tags.get("ResolutionUnit")
        if xres is not None and xres.value[0]:
            ppu = xres.value[0] / xres.value[1]  # pixels per resolution unit
            unit = int(runit.value) if runit else 2  # 2=inch, 3=cm
            # A writer default stamped in the file is worse than no value at
            # all: it converts cleanly and looks like a real reading.
            if unit == 2 and ppu in PLACEHOLDER_DPI:
                return None, f"placeholder {ppu:g} dpi tag (not a real pixel size)"
            per_um = {2: 25400.0, 3: 10000.0}.get(unit, 25400.0)
            return per_um / ppu, f"XResolution (unit={unit})"

    return None, "not found"


def _plausible(mpp: float | None, src: str) -> tuple[float | None, str]:
    """Reject pixel sizes no brightfield scanner would produce."""
    if mpp is None:
        return None, src
    if not (MPP_MIN <= mpp <= MPP_MAX):
        return None, f"implausible mpp {mpp:.5g} from {src}"
    return mpp, src


# Brightfield WSI pixel sizes live in roughly 0.1-2 um/px (40x to 5x). Anything
# outside this is a metadata artefact, not a scanner reading.
MPP_MIN, MPP_MAX = 0.05, 5.0

# Resolution tags that are library defaults rather than scanner readings. A
# plain TIFF writer stamps 72 or 96 dpi when the caller says nothing, which
# converts to a superficially valid 352.78 / 264.58 um/px.
PLACEHOLDER_DPI = {72.0, 96.0, 1.0}

DIMS_HE_MPP_RE = re.compile(r"HE=\d+x\d+\s*\([^)]*?mpp=([\d.eE+-]+)")


def load_dims_tsv(path: Path | None) -> dict[str, float]:
    """Return {biospecimen: H&E mpp} from a hande_codex_dims-style report.

    Lines look like::

        HTA11_999999026_1  DIFF  HE=27067x48324 (c=3, mpp=0.2525) CODEX=... ratio=...

    Only the H&E pixel size is taken; the CODEX side and the ratios are the
    registration story, not a patching input.
    """
    if path is None:
        return {}
    dims: dict[str, float] = {}
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            biospecimen = line.split("\t")[0].split()[0]
            m = DIMS_HE_MPP_RE.search(line)
            if m:
                dims[biospecimen] = float(m.group(1))
    return dims


def load_extra_mpp(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}
    extra: dict[str, float] = {}
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            value = (row.get("mpp") or "").strip()
            if value:
                extra[row["wsi"].strip()] = float(value)
    return extra


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=("coords", "feat"), default="coords",
                    help="coords: seg+patch job. feat: feature job (needs coords h5).")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--n-workers", type=int, default=N_WORKERS)
    ap.add_argument("--extra-mpp", type=Path, default=None,
                    help="CSV (wsi,mpp) supplying pixel sizes metadata lacks.")
    ap.add_argument("--dims-tsv", type=Path, default=None,
                    help="hande_codex_dims.tsv; supplies H&E mpp per biospecimen.")
    ap.add_argument("--default-mpp", type=float, default=None,
                    help="Fallback mpp for slides with no readable pixel size.")
    ap.add_argument("--force", action="store_true",
                    help="Include slides already finished for this stage.")
    args = ap.parse_args()

    if not args.data_dir.is_dir():
        print(f"[ERROR] Data directory not found: {args.data_dir}", file=sys.stderr)
        return 1
    if not args.manifest.is_file():
        print(f"[ERROR] Manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    for label, path in (("Dims TSV", args.dims_tsv), ("Extra-mpp CSV", args.extra_mpp)):
        if path is not None and not path.is_file():
            print(f"[ERROR] {label} not found: {path}", file=sys.stderr)
            return 1

    if args.stage == "coords":
        list_dir = args.out_dir / "process_lists"
        done_dir = args.out_dir / COORDS_SUBDIR / "patches"
        done_suffix = "_patches.h5"
        submit_script = "submit_htan_he_patch.sh"
    else:
        list_dir = args.out_dir / "process_lists_feat"
        done_dir = args.out_dir / COORDS_SUBDIR / f"features_{ENCODER}"
        done_suffix = ".h5"
        submit_script = "submit_htan_he_feat.sh"

    coords_dir = args.out_dir / COORDS_SUBDIR / "patches"

    he_rows = he_basenames_from_manifest(args.manifest)

    on_disk = {
        p.name: p
        for p in sorted(args.data_dir.iterdir())
        if p.is_file()
        and not p.name.startswith("._")
        and p.suffix.lower() in SLIDE_EXTS
    }

    he_present = sorted(name for name in on_disk if name in he_rows)
    spatial_or_unknown = sorted(name for name in on_disk if name not in he_rows)

    print(f"[INFO] Stage                  : {args.stage}")
    print(f"[INFO] Files on disk          : {len(on_disk)}")
    print(f"[INFO] H&E (role=histology)   : {len(he_present)}")
    print(f"[INFO] Non-H&E / not in manifest: {len(spatial_or_unknown)} (skipped)")

    missing = sorted(name for name in he_rows if name not in on_disk)
    if missing:
        print(f"[INFO] H&E in manifest, not downloaded: {len(missing)}")

    if not he_present:
        print("[ERROR] No H&E slides found on disk.", file=sys.stderr)
        return 1

    extra_mpp = load_extra_mpp(args.extra_mpp)
    dims_mpp = load_dims_tsv(args.dims_tsv)
    if args.dims_tsv:
        print(f"[INFO] Dims TSV entries       : {len(dims_mpp)}")

    # ---- Resume filter + mpp probe ----
    rows: list[tuple[str, float]] = []
    needs_mpp: list[str] = []
    n_done = 0
    n_no_coords = 0

    for name in he_present:
        stem = Path(name).stem  # "S026.ome.tif" -> "S026.ome", as TRIDENT names it
        h5 = done_dir / f"{stem}{done_suffix}"
        if not args.force and h5.is_file() and h5.stat().st_size > 0 \
                and not (done_dir / f"{stem}{done_suffix}.lock").exists():
            n_done += 1
            continue

        # Features are computed from existing coordinates.
        if args.stage == "feat":
            c_h5 = coords_dir / f"{stem}_patches.h5"
            if not c_h5.is_file() or c_h5.stat().st_size == 0 \
                    or (coords_dir / f"{stem}_patches.h5.lock").exists():
                n_no_coords += 1
                continue

        biospecimen = he_rows[name].get("biospecimen", "").strip()

        # Probe only when it can tell us something: either it is the source of
        # record, or it is the cross-check against a value we already have.
        known = name in extra_mpp or biospecimen in dims_mpp
        if known and tifffile is None:
            probed, probe_src = None, "not probed (no tifffile)"
        else:
            try:
                probed, probe_src = _plausible(*mpp_from_file(on_disk[name]))
            except Exception as err:  # unreadable/odd TIFF; report, don't abort
                probed, probe_src = None, f"ERROR: {err}"

        if name in extra_mpp:
            mpp, src = extra_mpp[name], "extra-mpp"
        elif biospecimen in dims_mpp:
            mpp, src = dims_mpp[biospecimen], f"dims-tsv ({biospecimen})"
            # The report and the file should agree; if they don't, one of them
            # is describing a different pyramid level.
            if probed and abs(probed - mpp) / mpp > 0.01:
                print(f"[WARN] mpp mismatch {name}: dims-tsv={mpp} "
                      f"file={probed:.5f} [{probe_src}] -- using dims-tsv")
        else:
            mpp, src = probed, probe_src

        if mpp is None or mpp <= 0:
            if args.default_mpp is not None:
                mpp, src = args.default_mpp, "default-mpp"
            else:
                needs_mpp.append(name)
                print(f"[WARN] no mpp  {name:45s} [{src}]")
                continue

        print(f"[INFO] mpp={mpp:<10.5f} {name:45s} [{src}]")
        rows.append((name, mpp))

    print("")
    print(f"[INFO] Already complete       : {n_done}")
    if args.stage == "feat" and n_no_coords:
        print(f"[WARN] Skipped (no coords h5) : {n_no_coords}")
        print("[WARN]   Re-run the coords stage for these first.")
    print(f"[INFO] Slides to process      : {len(rows)}")

    list_dir.mkdir(parents=True, exist_ok=True)

    if needs_mpp:
        nm_path = list_dir / "needs_mpp.csv"
        with nm_path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["wsi", "mpp"])
            for name in needs_mpp:
                w.writerow([name, ""])
        print(f"[WARN] {len(needs_mpp)} slide(s) have no readable pixel size -> {nm_path}")
        print("[WARN]   Fill in the mpp column and re-run with "
              f"--extra-mpp {nm_path}, or pass --default-mpp.")

    if not rows:
        print("[INFO] Nothing to do.")
        return 0

    # A comma in a filename would corrupt the two-column CSV.
    bad = [name for name, _ in rows if "," in name]
    if bad:
        print(f"[ERROR] Filename contains a comma: {bad}", file=sys.stderr)
        return 1

    n = len(rows)
    n_chunks = max(1, min(args.n_workers, n))
    chunk_size = (n + n_chunks - 1) // n_chunks

    for i in range(args.n_workers):
        csv_path = list_dir / f"chunk_{i}.csv"
        with csv_path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["wsi", "mpp"])
            for name, mpp in rows[i * chunk_size:(i + 1) * chunk_size]:
                w.writerow([name, mpp])
        count = max(0, len(rows[i * chunk_size:(i + 1) * chunk_size]))
        print(f"  chunk {i}: {count} slides -> {csv_path}")

    print("")
    print(f"[INFO] Done. Submit with: sbatch --array=0-{args.n_workers - 1} "
          f"scripts/{submit_script}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
