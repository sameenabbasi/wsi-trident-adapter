# CLI Reference

The project installs two entry points:

- `wsi-trident-adapter` – runs TRIDENT with profile-aware defaults.
- `wsi-trident-adapter-install` – performs profile setup.

Both commands return exit code `0` on success and emit diagnostic messages to
stderr when something fails.

---

## `wsi-trident-adapter`

### Synopsis

```
wsi-trident-adapter {run, script, config, profile, example} [options]
```

### Global options

| Flag | Description |
| ---- | ----------- |
| `-v`, `--version` | Print adapter version and exit. |

### `run`

Execute TRIDENT pipeline stages for the active profile.

```
wsi-trident-adapter run --task {all,seg,patch,feat} [options]
```

Configuration values resolve in the following order (lowest precedence
first): profile defaults → YAML file (`--config`) → command-line overrides
listed below. Use the additional flags for experiment-specific tweaks without
editing your baseline config.

| Option | Description |
| ------ | ----------- |
| `--task` (required) | Pipeline stage(s) to run: `all`, `seg`, `patch`, or `feat`. |
| `--config PATH` | YAML configuration file (see `docs/config-reference.md` and `configs/config_template.yaml`). |
| `--wsi-dir PATH` | Override `io.wsi_dir`. |
| `--process-list PATH` | CSV manifest for slide-specific options (see `docs/process-list.md`). |
| `--job-dir PATH` | Override `io.job_dir`. |
| `--seg-conf-thresh FLOAT` | Override `segmentation.seg_conf_thresh`. |
| `--encoder NAME` | Override `features.encoder`. |

Outputs are written under `<job_dir>/job_runs/<timestamp-id>/`.
Those run directories capture the exact config and generated process lists so
experiments can be reproduced later. The top-level `contours`, `patches`, and
`features_*` folders are reused across runs: TRIDENT skips work when outputs
already exist, so rerun in the same `job_dir` only when adding new feature
encoders or regenerating missing artifacts. If you truly need to redo
segmentation or patching, remove the corresponding files (e.g., `contours/`,
`contours_geojson/`, `patches/`) before launching the job.


### `script`

Print the SLURM submission template for the active profile.

```
wsi-trident-adapter script
```

The template includes module loads, environment exports, and invocation of the
`run` command. Write it to disk or pipe directly to a file.

### `config`

```
wsi-trident-adapter config
```

Print the built-in YAML defaults (same content as `configs/config_template.yaml`).
Use this to bootstrap a project-specific configuration.

### `profile`

Inspect metadata for the active profile.

Subcommands:

| Command | Output |
| ------- | ------ |
| `profile root` | Absolute path to the profile assets root. |
| `profile env` | Key-value pairs (`KEY=value`) excluding derived paths. |
| `profile modules` | Module list used by SLURM templates. |
| `profile show` | Summary containing modules, path hints, and profile notes. |

### `example`

Work with the bundled example dataset.

| Command | Description |
| ------- | ----------- |
| `example path` | Print the canonical example directory. |
| `example fetch [--dest PATH]` | Copy the example into `PATH` (defaults to current directory). |

---

## `wsi-trident-adapter-install`

Prepare a virtual environment by copying checkpoints and installing
profile-specific wheels.

### Synopsis

```
wsi-trident-adapter-install {setup,list-profiles} [...]
```

### Commands

| Command | Description |
| ------- | ----------- |
| `setup PROFILE` | Install requirements for `PROFILE`, copy checkpoint manifests, and record adapter state (used to resolve the active profile). |
| `list-profiles` | Print available profile names discovered under `trident_adapter/profiles/`. |

Typical workflow:

```bash
wsi-trident-adapter-install list-profiles
wsi-trident-adapter-install setup hpc-for-health
```
