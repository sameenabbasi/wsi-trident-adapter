"""Invoke a profile's install.sh helper."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import trident_adapter


def run_install_script(profile: str) -> None:
    adapter_root = Path(trident_adapter.__file__).resolve().parent
    profile_dir = adapter_root / "profiles" / profile
    install_sh = profile_dir / "install.sh"

    if not profile_dir.is_dir():
        raise RuntimeError(f"Profile directory not found: {profile_dir}")

    if not install_sh.is_file():
        raise RuntimeError(
            f"install.sh not found for profile '{profile}'. Expected at: {install_sh}"
        )

    subprocess.run(["bash", str(install_sh)], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a profile's install.sh helper")
    parser.add_argument("profile", help="Profile name under trident_adapter/profiles")
    args = parser.parse_args(argv)

    try:
        run_install_script(args.profile)
    except subprocess.CalledProcessError as exc:
        print(f"[trident-adapter-install] install.sh exited with {exc.returncode}", file=sys.stderr)
        return exc.returncode
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[trident-adapter-install] error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
