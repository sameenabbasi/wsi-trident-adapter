from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path

from importlib import resources

JOB_RUNS_DIRNAME = "job_runs"


def new_run_id() -> str:
    """Generate a timestamp-based run ID with a short random suffix."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = secrets.token_hex(2)  # 4 hex characters
    return f"{ts}-{suffix}"


def run_subdir(run_id: str) -> Path:
    """Return job_dir-relative path for the given run ID."""
    return Path(JOB_RUNS_DIRNAME) / run_id


def adapter_root() -> Path:
    """Return the installed trident_adapter package directory."""
    return Path(resources.files("trident_adapter"))


def profiles_dir() -> Path:
    """Return the profiles directory inside the package."""
    return adapter_root() / "profiles"


def profile_dir(profile: str) -> Path:
    """Return the directory for the given profile name."""
    return profiles_dir() / profile


def profile_toml(profile: str) -> Path:
    """Return the profile.toml path for the given profile."""
    return profile_dir(profile) / "profile.toml"


def assets_example_dir(assets_root: str | Path) -> Path:
    """Return the example directory under the provided assets root."""
    return Path(assets_root) / "example"
