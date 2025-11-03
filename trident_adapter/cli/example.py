from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .common import CLIError, print_cli_error
from ..core.profile import get_active_profile, resolve_example_path


def _run_example_path(args) -> Path:
    try:
        profile = get_active_profile()
        return resolve_example_path(profile)
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc


def run_cmd_example_path(args) -> int:
    try:
        example_dir = _run_example_path(args)
    except CLIError as exc:
        print_cli_error(exc)
        return exc.exit_code
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print(example_dir)
    return 0


def _run_example_fetch(args) -> Path:
    try:
        profile = get_active_profile()
        source = resolve_example_path(profile)
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc
    if not source.exists():
        raise CLIError(f"Example directory not found: {source}")

    dest_root = Path(args.dest)
    if dest_root.exists() and not dest_root.is_dir():
        raise CLIError(f"Destination is not a directory: {dest_root}")
    dest_root.mkdir(parents=True, exist_ok=True)

    target = dest_root / source.name
    if source.resolve() == target.resolve():
        raise CLIError("Source and destination paths are identical.")

    shutil.copytree(source, target, dirs_exist_ok=True)
    return target


def run_cmd_example_fetch(args) -> int:
    try:
        target = _run_example_fetch(args)
    except CLIError as exc:
        print_cli_error(exc)
        return exc.exit_code
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print(target)
    return 0
