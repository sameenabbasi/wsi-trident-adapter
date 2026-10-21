from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Config:
    @dataclass(frozen=True, slots=True)
    class IO:
        wsi_dir: Path
        job_dir: Path
        process_list: Path | None
        wsi_extension: tuple[str, ...]
        run_id: str | None = None

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
    class Normalization:
        enabled: bool
        method: str
        output_dir: Path
        reference_image: Path | None = None

    @dataclass(frozen=True, slots=True)
    class System:
        device: str

    io: IO
    segmentation: Segmentation
    patching: Patching
    features: Features
    normalization: Normalization
    system: System

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        io_data = data["io"]
        seg_data = data["segmentation"]
        patch_data = data["patching"]
        feat_data = data["features"]
        sys_data = data["system"]
        norm_data = data.get("normalization", {})
        ref = norm_data.get("reference_image")

        io = cls.IO(
            wsi_dir=Path(io_data["wsi_dir"]).expanduser().resolve(),
            job_dir=Path(io_data["job_dir"]).expanduser().resolve(),
            process_list=(
                Path(io_data["process_list"]).expanduser().resolve()
                if io_data.get("process_list")
                else None
            ),
            wsi_extension=tuple(io_data.get("wsi_extension", ())),
            run_id=io_data.get("run_id"),
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
            min_tissue_proportion=float(
                patch_data["min_tissue_proportion"]
            ),
        )

        features = cls.Features(
            encoder=feat_data["encoder"],
            batch_size=int(feat_data["batch_size"]),
        )

        normalization = cls.Normalization(
            enabled=bool(norm_data.get("enabled", False)),
            method=norm_data.get("method", "macenko"),
            output_dir=Path(
                norm_data.get("output_dir", "./out/normalized")
            ).expanduser().resolve(),
            reference_image=(
                Path(ref).expanduser().resolve() if ref else None
            ),
        )

        system = cls.System(device=sys_data["device"])

        return cls(
            io=io,
            segmentation=segmentation,
            patching=patching,
            features=features,
            normalization=normalization,
            system=system,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "io": {
                "wsi_dir": str(self.io.wsi_dir),
                "job_dir": str(self.io.job_dir),
                "process_list": (
                    str(self.io.process_list)
                    if self.io.process_list
                    else None
                ),
                "wsi_extension": list(self.io.wsi_extension),
                "run_id": self.io.run_id,
            },
            "segmentation": {
                "segmenter": self.segmentation.segmenter,
                "seg_conf_thresh": self.segmentation.seg_conf_thresh,
                "remove_artifacts": self.segmentation.remove_artifacts,
                "remove_holes": self.segmentation.remove_holes,
            },
            "patching": {
                "magnification": self.patching.magnification,
                "patch_size": self.patching.patch_size,
                "overlap": self.patching.overlap,
                "min_tissue_proportion": (
                    self.patching.min_tissue_proportion
                ),
            },
            "features": {
                "encoder": self.features.encoder,
                "batch_size": self.features.batch_size,
            },
            "normalization": {
                "enabled": self.normalization.enabled,
                "method": self.normalization.method,
                "output_dir": str(self.normalization.output_dir),
                "reference_image": (
                    str(self.normalization.reference_image)
                    if self.normalization.reference_image
                    else None
                ),
            },
            "system": {
                "device": self.system.device,
            },
        }
