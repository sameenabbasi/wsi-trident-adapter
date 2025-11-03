from __future__ import annotations

import sys

from .common import CLIError, print_cli_error
from ..core.profile import (
    get_active_profile,
    get_profile_env,
    get_profile_modules,
    get_profile_notes,
    resolve_example_path,
)


def _run_profile_root(args) -> str:
    try:
        profile = get_active_profile()
        example_dir = resolve_example_path(profile)
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc
    return str(example_dir.parent)


def run_cmd_profile_root(args) -> int:
    try:
        path_str = _run_profile_root(args)
    except CLIError as exc:
        print_cli_error(exc)
        return exc.exit_code
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print(path_str)
    return 0


def _run_profile_env(args) -> list[str]:
    try:
        profile = get_active_profile()
        env = get_profile_env(profile)
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc

    if not env:
        raise CLIError(
            f"Profile '{profile}' does not define any environment values."
        )

    return [f"{key}={value}" for key, value in sorted(env.items())]


def run_cmd_profile_env(args) -> int:
    try:
        lines = _run_profile_env(args)
    except CLIError as exc:
        print_cli_error(exc)
        return exc.exit_code
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    for line in lines:
        print(line)
    return 0


def _run_profile_modules(args) -> list[str]:
    try:
        profile = get_active_profile()
        modules = get_profile_modules(profile)
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc
    return modules


def run_cmd_profile_modules(args) -> int:
    try:
        modules = _run_profile_modules(args)
    except CLIError as exc:
        print_cli_error(exc)
        return exc.exit_code
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    is_tty = sys.stdout.isatty()
    if modules:
        for module in modules:
            print(module)
    elif is_tty:
        print("# No modules configured for this profile.")
        print("# Environment likely already provides required dependencies.")

    return 0


def _run_profile_show(args) -> list[str]:
    try:
        profile = get_active_profile()
        env = get_profile_env(profile)
        modules = get_profile_modules(profile)
        notes = get_profile_notes(profile)
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc

    lines: list[str] = [f"Active profile: {profile}", ""]

    lines.append("modules:")
    if modules:
        for module in modules:
            lines.append(f"  - {module}")
    else:
        lines.append("  (none)")

    lines.append("")
    path_items = [
        (key, value)
        for key, value in env.items()
        if key.upper() != "ASSETS_ROOT"
    ]
    lines.append("paths:")
    if path_items:
        width = max(len(name) for name, _ in path_items)
        for name, value in sorted(path_items):
            lines.append(f"  {name:<{width}} = {value}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("notes:")
    if notes:
        for note in notes:
            lines.append(f"  - {note}")
    else:
        lines.append("  (none)")

    return lines


def run_cmd_profile_show(args) -> int:
    try:
        lines = _run_profile_show(args)
    except CLIError as exc:
        print_cli_error(exc)
        return exc.exit_code
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    for line in lines:
        print(line)
    return 0
