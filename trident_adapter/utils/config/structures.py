from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class Config:
    @dataclass(frozen=True, slots=True)
    class IO:
        wsi_dir: Path
        job_dir: Path
        process_list: Path | None
        wsi_extension: tuple[str, ...]

    @dataclass(frozen=True, slots=True)
    class Segmentation:
        segmenter: str
        seg_conf_thresh: float
        remove_artifacts: bool
        remove_holes: bool

    @dataclass(frozen=True, slots=True)
    class Patching:
        magnification: int
        patch_size: int
        overlap: int
        min_tissue_proportion: float

    @dataclass(frozen=True, slots=True)
    class Features:
        encoder: str
        batch_size: int

    @dataclass(frozen=True, slots=True)
    class System:
        device: str

    io: IO
    segmentation: Segmentation
    patching: Patching
    features: Features
    system: System

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        io_data = data["io"]
        seg_data = data["segmentation"]
        patch_data = data["patching"]
        feat_data = data["features"]
        sys_data = data["system"]

        io = cls.IO(
            wsi_dir=Path(io_data["wsi_dir"]),
            job_dir=Path(io_data["job_dir"]),
            process_list=(
                Path(io_data["process_list"])
                if io_data.get("process_list")
                else None
            ),
            wsi_extension=tuple(io_data.get("wsi_extension", ())),
        )

        segmentation = cls.Segmentation(
            segmenter=seg_data["segmenter"],
            seg_conf_thresh=float(seg_data["seg_conf_thresh"]),
            remove_artifacts=bool(seg_data["remove_artifacts"]),
            remove_holes=bool(seg_data["remove_holes"]),
        )

        patching = cls.Patching(
            magnification=int(patch_data["magnification"]),
            patch_size=int(patch_data["patch_size"]),
            overlap=int(patch_data["overlap"]),
            min_tissue_proportion=float(patch_data["min_tissue_proportion"]),
        )

        features = cls.Features(
            encoder=feat_data["encoder"],
            batch_size=int(feat_data["batch_size"]),
        )

        system = cls.System(device=sys_data["device"])

        return cls(
            io=io,
            segmentation=segmentation,
            patching=patching,
            features=features,
            system=system,
        )
