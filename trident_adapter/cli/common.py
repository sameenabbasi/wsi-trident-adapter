from __future__ import annotations

import sys


class CLIError(RuntimeError):
    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def print_cli_error(exc: CLIError) -> None:
    for line in str(exc).splitlines():
        print(line, file=sys.stderr)
