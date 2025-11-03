from __future__ import annotations

import argparse
from pathlib import Path

from .. import __version__
from .profile import (
    run_cmd_profile_env,
    run_cmd_profile_modules,
    run_cmd_profile_root,
    run_cmd_profile_show,
)
from .config import run_cmd_config
from .example import run_cmd_example_fetch, run_cmd_example_path
from .run import run_cmd_run
from .script import run_cmd_script


def _configure_pipeline_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--task",
        choices=["all", "seg", "patch", "feat"],
        default="all",
        required=True,
        help="Which pipeline stage(s) to run. Default: all.",
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Optional YAML config file. CLI flags override values in config.",
    )

    parser.add_argument(
        "--wsi-dir",
        type=Path,
        help="Path to folder containing whole-slide images (.svs, .tif, ...).",
    )

    parser.add_argument(
        "--process-list",
        type=Path,
        help=(
            "CSV file mapping slide_id to threshold. When provided, overrides "
            "--seg-conf-thresh and limits processing to listed slides."
        ),
    )

    parser.add_argument(
        "--job-dir",
        type=Path,
        help="Directory where extracted features will be saved.",
    )

    parser.add_argument(
        "--seg-conf-thresh",
        type=float,
        help="Global segmentation threshold (float between 0 and 1).",
    )

    parser.add_argument(
        "--encoder",
        type=str,
        help="Patch encoder to use (e.g., uni_v2, resnet50).",
    )


def _add_run(subparsers: argparse._SubParsersAction) -> None:
    run_parser = subparsers.add_parser(
        "run",
        help="Execute TRIDENT adapter tasks.",
        description="Run TRIDENT pipeline stages for the active profile.",
    )

    _configure_pipeline_parser(run_parser)
    run_parser.set_defaults(handler=run_cmd_run)


def _add_script(subparsers: argparse._SubParsersAction) -> None:
    script_parser = subparsers.add_parser(
        "script",
        help="Generate a SLURM script template for the adapter.",
        description=(
            "Create a SLURM submission script that invokes the adapter with "
            "the supplied arguments."
        ),
    )

    script_parser.set_defaults(handler=run_cmd_script)


def _add_config(subparsers: argparse._SubParsersAction) -> None:
    config_parser = subparsers.add_parser(
        "config",
        help="Print the default configuration in YAML format.",
        description="Print the built-in configuration template.",
    )

    config_parser.set_defaults(handler=run_cmd_config)


def _add_profile(subparsers: argparse._SubParsersAction) -> None:
    profile_parser = subparsers.add_parser(
        "profile",
        help="Inspect active profile information.",
        description=(
            "Inspect paths and environment variables for the active profile."
        ),
    )

    profile_subparsers = profile_parser.add_subparsers(
        dest="profile_cmd", required=True
    )

    profile_root_parser = profile_subparsers.add_parser(
        "root",
        help="Print the assets root path.",
        description="Print the assets root path for the active profile.",
    )
    profile_root_parser.set_defaults(handler=run_cmd_profile_root)

    profile_env_parser = profile_subparsers.add_parser(
        "env",
        help="Print key adapter environment variables.",
        description=(
            "Print TRIDENT adapter environment variables in key=value form."
        ),
    )
    profile_env_parser.set_defaults(handler=run_cmd_profile_env)

    profile_show_parser = profile_subparsers.add_parser(
        "show",
        help="Display full profile information.",
        description="Display modules, paths, and notes for the active profile.",
    )
    profile_show_parser.set_defaults(handler=run_cmd_profile_show)

    profile_modules_parser = profile_subparsers.add_parser(
        "modules",
        help="List module requirements for the active profile.",
        description="Print the module load list for the active profile.",
    )
    profile_modules_parser.set_defaults(handler=run_cmd_profile_modules)


def _add_example(subparsers: argparse._SubParsersAction) -> None:
    example_parser = subparsers.add_parser(
        "example",
        help="Work with bundled example datasets.",
        description=(
            "Inspect or copy example datasets bundled with the adapter."
        ),
    )

    example_subparsers = example_parser.add_subparsers(
        dest="example_cmd", required=True
    )

    example_path_parser = example_subparsers.add_parser(
        "path",
        help="Print the example dataset path.",
        description="Print the path to the preinstalled example dataset.",
    )
    example_path_parser.set_defaults(handler=run_cmd_example_path)

    example_fetch_parser = example_subparsers.add_parser(
        "fetch",
        help="Copy the example dataset to a destination.",
        description="Copy the example dataset to the specified destination.",
    )
    example_fetch_parser.add_argument(
        "--dest",
        type=Path,
        default=Path("."),
        help=(
            "Destination directory for the example dataset (default: current"
            " directory)."
        ),
    )
    example_fetch_parser.set_defaults(handler=run_cmd_example_fetch)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="wsi-trident-adapter",
        description=(
            "Adapter around TRIDENT for whole-slide image (WSI) feature "
            "extraction. Provides a stable interface for HPC and offline use."
        ),
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="cmd", required=True)
    _add_run(subparsers)
    _add_script(subparsers)
    _add_config(subparsers)
    _add_profile(subparsers)
    _add_example(subparsers)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    handler = getattr(args, "handler", None)
    if handler is None:
        raise NotImplementedError(
            "No handler defined for the selected command."
        )

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
