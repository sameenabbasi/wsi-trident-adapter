from __future__ import annotations

import sys
from copy import deepcopy
import traceback

from .common import CLIError, print_cli_error
from ..core.profile import get_active_profile, resolve_profile_dir
from ..utils import paths
from ..core.config.defaults import DEFAULTS
from ..core.config.io import dump_yaml, load_yaml, merge
from ..core.config.structures import Config
from ..core.config.validation import (
    validate_config,
    validate_yaml_structure,
)


def _run_run(args) -> None:
    try:
        profile = get_active_profile()
        resolve_profile_dir(profile)
    except RuntimeError as exc:
        raise CLIError(str(exc)) from exc

    run_id = paths.new_run_id()

    base_config = deepcopy(DEFAULTS)
    file_config = load_yaml(args.config)
    structure_errors = validate_yaml_structure(file_config)
    if structure_errors:
        raise CLIError(
            "\n".join(f"[config] {msg}" for msg in structure_errors),
            exit_code=2,
        )

    runtime_config = merge(base_config, file_config)

    if args.wsi_dir:
        runtime_config["io"]["wsi_dir"] = args.wsi_dir

    if args.job_dir:
        runtime_config["io"]["job_dir"] = args.job_dir

    if args.process_list:
        runtime_config["io"]["process_list"] = args.process_list

    if args.seg_conf_thresh:
        runtime_config["segmentation"]["seg_conf_thresh"] = args.seg_conf_thresh

    if args.encoder:
        runtime_config["features"]["encoder"] = args.encoder

    runtime_config["io"]["run_id"] = run_id

    validation_errors = validate_config(runtime_config)
    if validation_errors:
        raise CLIError(
            "\n".join(f"[validation] {msg}" for msg in validation_errors)
        )

    runtime_config = Config.from_dict(runtime_config)

    run_directory = runtime_config.io.job_dir / paths.run_subdir(run_id)
    run_directory.mkdir(parents=True, exist_ok=True)
    dump_yaml(runtime_config, run_directory / "config.yaml")

    from ..runner import run_pipeline

    run_pipeline(
        config=runtime_config,
        task=args.task,
        run_dir=run_directory,
    )


def run_cmd_run(args) -> int:
    try:
        _run_run(args)
    except CLIError as exc:
        print_cli_error(exc)
        return exc.exit_code
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1
    return 0
