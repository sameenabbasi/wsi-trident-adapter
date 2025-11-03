from __future__ import annotations

import sys

from .common import CLIError, print_cli_error
from ..core.profile import get_active_profile, resolve_profile_dir


def _run_script(args) -> str:
    try:
        profile = get_active_profile()
        directory = resolve_profile_dir(profile)
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc
    template_path = directory / "slurm_template.sh"
    if not template_path.exists():
        raise CLIError(
            f"Profile '{profile}' is missing slurm_template.sh at"
            f" {template_path}"
        )

    return template_path.read_text(encoding="utf-8")


def run_cmd_script(args) -> int:
    try:
        content = _run_script(args)
    except CLIError as exc:
        print_cli_error(exc)
        return exc.exit_code
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if content:
        print(content, end="" if content.endswith("\n") else "\n")

    return 0
