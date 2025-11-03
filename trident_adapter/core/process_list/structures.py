from __future__ import annotations

from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True, slots=True)
class ProcessList:
    """Validated process list and related flags."""

    df: pd.DataFrame
    has_threshold: bool
    has_mpp: bool

    @property
    def wsis(self) -> list[str]:
        return self.df["wsi"].tolist()
