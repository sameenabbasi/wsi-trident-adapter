from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from trident_adapter.utils import adapter_state, paths

from . import copy_ckpts, install_reqs


def _validate_profile(profile: str) -> Path:
    profile_dir = paths.profile_dir(profile)
    if not profile_dir.is_dir():
        raise RuntimeError(f"Profile directory not found: {profile_dir}")

    return profile_dir


def _record_adapter_state(profile: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    adapter_state.write_adapter_state({
        "profile": profile,
        "installed_at": timestamp,
    })


def _run_setup(profile: str) -> None:
    _validate_profile(profile)

    print("[install] Installing requirements...")
    install_reqs.install_requirements(profile)

    print(
        f"[copy-ckpts] Copying checkpoint manifests for profile '{profile}'..."
    )
    copy_ckpts.copy_ckpts(profile)

    _record_adapter_state(profile)
    print("[ok] Active profile recorded in adapter-state.json")
    print(f"[ok] Setup complete for profile '{profile}'")


def run_cmd_setup(args: argparse.Namespace) -> int:
    try:
        _run_setup(args.profile)
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    return 0


def _run_list_profiles() -> None:
    profiles_dir = paths.profiles_dir()
    if not profiles_dir.is_dir():
        raise RuntimeError(f"Profiles directory not found: {profiles_dir}")

    profiles = list(
        sorted(entry.name for entry in profiles_dir.iterdir() if entry.is_dir())
    )
    for name in profiles:
        print(name)


def run_cmd_list_profiles(args: argparse.Namespace) -> int:
    try:
        _run_list_profiles()
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    return 0


def _add_setup(subparsers: argparse._SubParsersAction) -> None:
    setup_parser = subparsers.add_parser(
        "setup",
        help=(
            "Install requirements, copy checkpoints, and record adapter state."
        ),
        description=(
            "Install requirements, copy checkpoints, and record adapter state."
        ),
    )
    setup_parser.add_argument(
        "profile",
        help="Profile name under trident_adapter/profiles",
    )
    setup_parser.set_defaults(handler=run_cmd_setup)


def _add_list_profiles(subparsers: argparse._SubParsersAction) -> None:
    list_parser = subparsers.add_parser(
        "list-profiles",
        help="List all available adapter profiles.",
        description=(
            "List every profile directory under trident_adapter/profiles."
        ),
    )
    list_parser.set_defaults(handler=run_cmd_list_profiles)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="wsi-trident-adapter-install",
        description=(
            "Install TRIDENT adapter profiles and manage adapter state."
        ),
    )

    subparsers = parser.add_subparsers(dest="cmd", required=True)
    _add_setup(subparsers)
    _add_list_profiles(subparsers)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
