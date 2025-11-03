from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

import trident_adapter

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


def _load_profile_modules(profile_toml: Path) -> list[str]:
    try:
        with profile_toml.open("rb") as handle:
            data = tomllib.load(handle)

    except Exception as exc:
        profile_name = profile_toml.parent.name
        raise RuntimeError(
            f"Invalid profile '{profile_name}': unable to read profile.toml at "
            f"{profile_toml}: {exc}"
        ) from exc

    modules = data.get("modules", [])
    if not isinstance(modules, list):
        return []

    return [str(module) for module in modules if module]


def install_requirements(profile: str) -> None:
    adapter_root = Path(trident_adapter.__file__).resolve().parent
    profile_dir = adapter_root / "profiles" / profile

    if not profile_dir.is_dir():
        raise RuntimeError(f"Profile directory not found: {profile_dir}")

    profile_toml = profile_dir / "profile.toml"
    if not profile_toml.exists():
        raise RuntimeError(
            f"Invalid profile '{profile}': missing profile.toml at"
            f" {profile_toml}"
        )

    req_file = profile_dir / "requirements.txt"
    if not req_file.exists():
        raise RuntimeError(
            f"Invalid profile '{profile}': missing requirements.txt at"
            f" {req_file}"
        )

    modules = _load_profile_modules(profile_toml)

    print(f"[install-requirements] Installing from {req_file}")
    if modules:
        module_list = " ".join(shlex.quote(module) for module in modules)

        pip_cmd = (
            f"{shlex.quote(sys.executable)} -m pip install -r "
            f"{shlex.quote(str(req_file))} --no-cache-dir"
        )

        command = f"module load {module_list} && {pip_cmd}"

        print(f"[install-requirements] Loading modules: {', '.join(modules)}")
        subprocess.run(["bash", "-lc", command], check=True)

    else:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(req_file),
                "--no-cache-dir",
            ],
            check=True,
        )
