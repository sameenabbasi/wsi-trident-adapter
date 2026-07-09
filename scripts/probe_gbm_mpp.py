#!/usr/bin/env python3
"""Read microns-per-pixel from OME-TIFF / qptiff metadata.

    python probe_mpp.py /cluster/projects/kumargroup/codex/gbm/raw
"""
import sys, glob, os, re
import tifffile

def mpp_from_file(path):
    with tifffile.TiffFile(path) as tf:
        # 1) OME-XML PhysicalSizeX (microns)
        ome = tf.ome_metadata
        if ome:
            m = re.search(r'PhysicalSizeX="([\d.]+)"', ome)
            u = re.search(r'PhysicalSizeXUnit="([^"]+)"', ome)
            if m:
                val = float(m.group(1))
                unit = (u.group(1) if u else "µm")
                if unit in ("nm",):        val /= 1000.0
                elif unit in ("mm",):      val *= 1000.0
                return val, f"OME PhysicalSizeX ({unit})"
        # 2) TIFF resolution tags (fallback; Akoya qptiff)
        p = tf.pages[0]
        xres = p.tags.get("XResolution")
        runit = p.tags.get("ResolutionUnit")
        if xres is not None and xres.value[0]:
            ppu = xres.value[0] / xres.value[1]          # pixels per unit
            unit = runit.value if runit else 2           # 2=inch, 3=cm
            per_um = {2: 25400.0, 3: 10000.0}.get(int(unit), 25400.0)
            return per_um / ppu, f"XResolution (unit={unit})"
    return None, "not found"

root = sys.argv[1] if len(sys.argv) > 1 else "."
files = sorted(glob.glob(os.path.join(root, "HE__*.tif")) +
               glob.glob(os.path.join(root, "HE__*.tiff")) +
               glob.glob(os.path.join(root, "WSI_HE__*.qptiff")))
for f in files:
    try:
        mpp, src = mpp_from_file(f)
    except Exception as e:
        mpp, src = None, f"ERROR: {e}"
    print(f"{mpp!s:>10}  {os.path.basename(f):55s}  [{src}]")
