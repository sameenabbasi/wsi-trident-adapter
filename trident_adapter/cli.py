import argparse
import sys
from copy import deepcopy
from pathlib import Path
from textwrap import dedent

from . import __version__
from .config import DEFAULTS
from .utils.config.io import load_yaml, merge
from .utils.config.validation import validate_config, validate_yaml_structure
from .utils.config.structures import Config


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
        default="uni_v2",
        help="Patch encoder to use (e.g., uni_v2, resnet50).",
    )


def _add_extract(subparsers: argparse._SubParsersAction) -> None:
    extract_parser = subparsers.add_parser(
        "extract",
        help="Run TRIDENT pipeline via adapter (all | seg | patch | feat).",
        description=(
            "Perform tissue segmentation, patching, and patch-level feature "
            "extraction on whole-slide images. Supports either a global "
            "segmentation threshold or a CSV with per-slide thresholds."
        ),
    )

    _configure_pipeline_parser(extract_parser)
    extract_parser.set_defaults(cmd="extract")


def _add_script(subparsers: argparse._SubParsersAction) -> None:
    script_parser = subparsers.add_parser(
        "script",
        help="Generate a SLURM script template for the adapter.",
        description=(
            "Create a SLURM submission script that invokes the adapter with "
            "the supplied arguments."
        ),
    )

    _configure_pipeline_parser(script_parser)
    script_parser.set_defaults(cmd="script")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the adapter."""
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
    _add_extract(subparsers)
    _add_script(subparsers)

    return parser.parse_args(argv)


def run_cmd_extract(args: argparse.Namespace) -> int:
    base_config = deepcopy(DEFAULTS)
    file_config = load_yaml(args.config)
    structure_errors = validate_yaml_structure(file_config)
    if structure_errors:
        for msg in structure_errors:
            print(f"[config] {msg}", file=sys.stderr)
        return 2

    runtime_config = merge(base_config, file_config)

    if args.wsi_dir:
        runtime_config["io"]["wsi_dir"] = args.wsi_dir

    if args.output_dir:
        runtime_config["io"]["job_dir"] = args.job_dir

    if args.process_list:
        runtime_config["io"]["process_list"] = args.process_list

    if args.seg_conf_thresh:
        runtime_config["segmentation"]["seg_conf_thresh"] = args.seg_conf_thresh

    if args.encoder:
        runtime_config["features"]["encoder"] = args.encoder

    validation_errors = validate_config(runtime_config)
    if validation_errors:
        for msg in validation_errors:
            print(f"[validation] {msg}", file=sys.stderr)
        return 1

    runtime_config = Config.from_dict(runtime_config)

    from .runner import run_pipeline

    run_pipeline(config=runtime_config, task=args.task)

    return 0


def run_cmd_script(args: argparse.Namespace) -> int:
    flags = []

    if args.task:
        flags.append(f'--task "{args.task}"')

    if args.wsi_dir:
        flags.append(f'--wsi-dir "{args.wsi_dir}"')

    if args.job_dir:
        flags.append(f'--job-dir "{args.job_dir}"')

    if args.process_list:
        flags.append(f'--process-list "{args.process_list}"')

    if args.seg_conf_thresh:
        flags.append(f"--seg-conf-thresh {args.seg_conf_thresh}")

    if args.encoder:
        flags.append(f'--encoder "{args.encoder}"')

    flags = " ".join(flags)

    slurm_script = f"""
    #!/bin/bash
    #SBATCH -c 8
    #SBATCH --mem 32G
    #SBATCH --gres gpu:1
    #SBATCH -A kumargroup_gpu
    #SBATCH -t 1:00:00:00
    #SBATCH -J example
    #SBATCH -o out/stdout.txt
    #SBATCH -e out/stderr.txt

    # ===== Environment setup =====
    export HF_HOME="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/huggingface"
    export TORCH_HOME="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/torch"
    export TRIDENT_HOME="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/trident"
    # ==============================

    wsi-trident-adapter extract {flags}
    """

    print(dedent(slurm_script).strip())

    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.cmd == "script":
        return run_cmd_script(args)

    if args.cmd == "extract":
        return run_cmd_extract(args)

    print(f"[cli] unknown command: {args.cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
