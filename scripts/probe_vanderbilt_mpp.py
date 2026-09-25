#!/usr/bin/env python3
"""Report which metadata branch supplies (or fails to supply) an mpp for the
Vanderbilt (HTA11_*) H&E slides.

    python scripts/probe_vanderbilt_mpp.py
    python scripts/probe_vanderbilt_mpp.py --csv /tmp/vanderbilt_mpp.csv

prepare_htan_he_lists.py resolves these slides' pixel size from the file
itself -- the CODEX dims TSV is keyed on biospecimen and covers only the
CODEX pairs, so MxIF falls through to mpp_from_file().  17 of the 30
Vanderbilt slides got a value and 13 landed in needs_mpp.csv, with nothing in
the manifest to tell them apart, so the difference is inside the files.

Each of the three branches is reported independently, so a slide that
resolved via OME PhysicalSizeX (a real reading) is distinguishable from one
that resolved via XResolution (often a writer default).

Page 0's ImageDescription is also re-read directly.  tifffile populates
``ome_metadata`` only when it recognises the file as OME, so a file can carry
perfectly good OME-XML that the pipeline never looks at; BRANCH=raw-ome marks
that case -- those slides are recoverable without inventing a pixel size.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

try:
    import tifffile
except ModuleNotFoundError:
    sys.exit("tifffile not installed -- conda activate methylcdm_h100")

DATA_DIR = Path("/cluster/projects/kumargroup/sean/data/HTAN_SPATIAL_PROTEOMICS")
NEEDS_MPP = DATA_DIR / "processed/process_lists/needs_mpp.csv"

# Mirrors prepare_htan_he_lists.py so the verdicts here match what that script did.
MPP_MIN, MPP_MAX = 0.05, 5.0
PLACEHOLDER_DPI = {72.0, 96.0, 1.0}

PSX = re.compile(r'PhysicalSizeX="([\d.eE+-]+)"')
PSX_UNIT = re.compile(r'PhysicalSizeXUnit="([^"]+)"')
PSY = re.compile(r'PhysicalSizeY="([\d.eE+-]+)"')


def _scale(val: float, unit: str) -> float:
    return val / 1000.0 if unit == "nm" else val * 1000.0 if unit == "mm" else val


def ome_psx(xml: str | None):
    """(mpp, unit, psy) from an OME-XML string, or (None, None, None)."""
    if not xml:
        return None, None, None
    m = PSX.search(xml)
    if not m:
        return None, None, None
    unit = (PSX_UNIT.search(xml).group(1) if PSX_UNIT.search(xml) else "um")
    y = PSY.search(xml)
    return _scale(float(m.group(1)), unit), unit, (_scale(float(y.group(1)), unit) if y else None)


def plausible(mpp):
    return mpp is not None and MPP_MIN <= mpp <= MPP_MAX


def probe(path: Path) -> dict:
    r = {"file": path.name, "shape": "", "pages": "", "ome_attr": "", "psx_attr": "",
         "psx_raw": "", "unit": "", "anisotropic": "", "aperio": "", "xres_mpp": "",
         "xres_note": "", "branch": "", "mpp": "", "note": ""}
    with tifffile.TiffFile(path) as tf:
        p0 = tf.pages[0]
        r["shape"] = "x".join(str(s) for s in p0.shape)
        r["pages"] = len(tf.pages)

        # 1a) what the pipeline sees
        attr_mpp, attr_unit, attr_y = ome_psx(tf.ome_metadata)
        r["ome_attr"] = "yes" if tf.ome_metadata else "no"
        r["psx_attr"] = f"{attr_mpp:.5f}" if attr_mpp else ""

        # 1b) OME-XML sitting in the description that tifffile did not classify
        desc = p0.description or ""
        raw_mpp, raw_unit, raw_y = ome_psx(desc) if "<OME" in desc or "PhysicalSizeX" in desc else (None, None, None)
        r["psx_raw"] = f"{raw_mpp:.5f}" if raw_mpp else ""
        r["unit"] = attr_unit or raw_unit or ""

        psx, psy = (attr_mpp or raw_mpp), (attr_y or raw_y)
        if psx and psy and abs(psx - psy) / psx > 0.01:
            r["anisotropic"] = f"Y={psy:.5f}"

        # 2) Aperio
        if "Aperio" in desc or "MPP" in desc:
            m = re.search(r"\bMPP\s*=\s*([\d.eE+-]+)", desc)
            if m:
                r["aperio"] = f"{float(m.group(1)):.5f}"

        # 3) XResolution
        xres, runit = p0.tags.get("XResolution"), p0.tags.get("ResolutionUnit")
        if xres is not None and xres.value[0]:
            ppu = xres.value[0] / xres.value[1]
            unit = int(runit.value) if runit else 2
            if unit == 2 and ppu in PLACEHOLDER_DPI:
                r["xres_note"] = f"placeholder {ppu:g}dpi"
            else:
                per_um = {2: 25400.0, 3: 10000.0}.get(unit, 25400.0)
                r["xres_mpp"] = f"{per_um / ppu:.5f}"
                r["xres_note"] = f"{ppu:g}/unit{unit}"
        else:
            r["xres_note"] = "no tag"

    # Which branch wins, and would it beat the plausibility gate?
    for label, val in (("ome", attr_mpp), ("aperio", float(r["aperio"]) if r["aperio"] else None),
                       ("xres", float(r["xres_mpp"]) if r["xres_mpp"] else None)):
        if val is not None:
            r["branch"], r["mpp"] = label, f"{val:.5f}"
            if not plausible(val):
                r["branch"], r["note"] = "none", f"rejected implausible {val:.5g} from {label}"
                r["mpp"] = ""
            break
    else:
        if raw_mpp is not None and plausible(raw_mpp):
            r["branch"], r["mpp"] = "raw-ome", f"{raw_mpp:.5f}"
            r["note"] = "OME-XML present but tifffile did not flag file as OME -- pipeline misses it"
        else:
            r["branch"] = "none"
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--glob", default="HTA11_*.tif")
    ap.add_argument("--needs-mpp", type=Path, default=NEEDS_MPP)
    ap.add_argument("--csv", type=Path, default=None, help="also write a full report here")
    args = ap.parse_args()

    parked = set()
    if args.needs_mpp.is_file():
        with args.needs_mpp.open(newline="") as fh:
            parked = {row["wsi"].strip() for row in csv.DictReader(fh) if row.get("wsi")}

    files = sorted(args.data_dir.glob(args.glob))
    if not files:
        print(f"[ERROR] No files match {args.glob} in {args.data_dir}", file=sys.stderr)
        return 1
    print(f"[INFO] {len(files)} file(s) matching {args.glob}\n")

    hdr = f"{'STATUS':<9}{'FILE':<26}{'BRANCH':<9}{'MPP':<10}{'OME?':<6}{'PSX':<10}{'XRES':<10}{'SHAPE':<16}NOTE"
    print(hdr); print("-" * len(hdr))

    rows, by_branch, parked_by_branch = [], {}, {}
    for f in files:
        try:
            r = probe(f)
        except Exception as err:
            print(f"{'ERROR':<9}{f.name[:25]:<26}{err}")
            rows.append({"file": f.name, "branch": "error", "note": str(err)})
            continue
        r["status"] = "PARKED" if f.name in parked else "ok"
        rows.append(r)
        by_branch[r["branch"]] = by_branch.get(r["branch"], 0) + 1
        if r["status"] == "PARKED":
            parked_by_branch[r["branch"]] = parked_by_branch.get(r["branch"], 0) + 1
        note = "; ".join(x for x in (r["note"], r["xres_note"] if r["branch"] != "xres" else "",
                                     r["anisotropic"]) if x)
        psx = r["psx_attr"] or r["psx_raw"]
        print(f"{r['status']:<9}{r['file'][:25]:<26}{r['branch']:<9}{r['mpp'][:9]:<10}"
              f"{r['ome_attr']:<6}{psx[:9]:<10}{r['xres_mpp'][:9]:<10}"
              f"{r['shape'][:15]:<16}{note}")

    print("\n=== where the mpp came from ===")
    for b, n in sorted(by_branch.items(), key=lambda kv: -kv[1]):
        flag = {"ome": "  <- real reading",
                "raw-ome": "  <- RECOVERABLE: pipeline is not reading this",
                "xres": "  <- writer tag, verify before trusting",
                "none": "  <- parked in needs_mpp.csv"}.get(b, "")
        print(f"  {b:<10} {n:>4}   (parked: {parked_by_branch.get(b, 0)}){flag}")

    mismatch = [r for r in rows if r.get("status") == "PARKED" and r.get("branch") not in ("none", "error")]
    if mismatch:
        print(f"\n[WARN] {len(mismatch)} slide(s) are in needs_mpp.csv but DO yield an mpp now.")
        print("[WARN]   Re-running prepare would pick them up; check tifffile versions match.")

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        cols = ["status", "file", "branch", "mpp", "ome_attr", "psx_attr", "psx_raw", "unit",
                "anisotropic", "aperio", "xres_mpp", "xres_note", "shape", "pages", "note"]
        with args.csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"\n[INFO] Full report -> {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
