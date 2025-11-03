import json
from importlib import resources
from pathlib import Path


def _get_state_path() -> Path:
    return Path(resources.files("trident_adapter")) / "adapter-state.json"


def read_adapter_state() -> dict:
    path = _get_state_path()
    if not path.exists():
        return {}

    with path.open("r") as f:
        return json.load(f)


def write_adapter_state(data: dict) -> None:
    path = _get_state_path()
    with path.open("w") as f:
        json.dump(data, f, indent=4)
