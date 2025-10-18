from pathlib import Path

import yaml


def load_yaml(path: Path | None) -> dict:
    if path is None:
        return {}

    with path.open("r") as f:
        return yaml.safe_load(f)


def merge(base: dict, override: dict) -> dict:
    merged = base.copy()
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = merge(merged[k], v)
        else:
            merged[k] = v

    return merged