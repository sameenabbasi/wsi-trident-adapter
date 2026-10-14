
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


class MacenkoNormalizer:
    """Thin wrapper around torchstain's Macenko normalizer."""

    def __init__(self, reference_image: str | Path):
        import torchstain

        self.reference_image = Path(reference_image)
        if not self.reference_image.is_file():
            raise FileNotFoundError(
                f"Reference image not found: {self.reference_image}"
            )

        self._normalizer = torchstain.normalizers.MacenkoNormalizer(
            backend="numpy"
        )

        reference = np.asarray(
            Image.open(self.reference_image).convert("RGB")
        )
        self._normalizer.fit(reference)

    def normalize(self, image: Image.Image) -> Image.Image:
        """Return a normalized RGB image without changing the input."""
        source = np.asarray(image.convert("RGB"))

        result = self._normalizer.normalize(I=source)

        # Handle the normalized image returned by the library.
        normalized = result[0] if isinstance(result, tuple) else result
        normalized = np.asarray(normalized)

        if normalized.ndim != 3 or normalized.shape[-1] != 3:
            raise ValueError(
                "torchstain returned an unexpected image shape: "
                f"{normalized.shape}"
            )

        if normalized.dtype != np.uint8:
            normalized = np.clip(normalized, 0, 255).astype(np.uint8)

        return Image.fromarray(normalized, mode="RGB")

    def normalize_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
    ) -> Path:
        """Normalize an image file and save it to a separate destination."""
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(input_path) as image:
            normalized = self.normalize(image)

        normalized.save(output_path)
        return output_path
