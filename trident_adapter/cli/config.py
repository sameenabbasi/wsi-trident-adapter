from __future__ import annotations

import sys

import yaml

from .common import CLIError, print_cli_error
from ..core.profile import get_active_profile
from ..core.config.defaults import DEFAULTS


def _run_config() -> str:
    try:
        get_active_profile()
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc
    return yaml.safe_dump(
        DEFAULTS,
        sort_keys=False,
        indent=4,
        default_flow_style=False,
    )


def run_cmd_config(args) -> int:
    try:
        output = _run_config()
    except CLIError as exc:
        print_cli_error(exc)
        return exc.exit_code
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print(output, end="")
    return 0
