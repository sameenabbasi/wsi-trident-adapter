# Installation – HPC for Health

This guide walks through preparing a Python environment on the HPC4Health
cluster and installing the adapter with the `hpc-for-health` profile.

## Prerequisites

-   Asset bundle staged at `/cluster/projects/kumargroup/wsi-trident-adapter-assets`
    (contact the maintainers if it is missing).
-   Recent Python module (`module avail python`)

## 1. Create a project directory

```bash
mkdir -p ~/wsi-trident-adapter
cd ~/wsi-trident-adapter
```

## 2. Load Python and create a virtual environment

HPC4Health provides site-managed Python builds. Use any Python ≥3.10:

```bash
module load python3/3.12
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

If you prefer Conda or Mamba, activate that environment instead of creating a
`venv`. The remaining steps assume the environment is active.

## 3. Install the adapter

```bash
pip install "git+https://github.com/haydenych/wsi-trident-adapter.git@v0.2.0"
```

Verify that the console scripts are available:

```bash
wsi-trident-adapter --version
wsi-trident-adapter-install --help
```

## 4. Configure the `hpc-for-health` profile

Run the installer once per environment to record the active profile and copy
checkpoint manifests:

```bash
# Run heavy setup on a build node to avoid stressing the login node.
salloc -p build -t 1:00:00 --mem 4G
```

Inside the allocation, activate your environment and run:

```bash
wsi-trident-adapter-install setup hpc-for-health
```

`setup` invokes Python extensively, so avoid running it on `h4huhnlogin1`. The
command installs profile-specific wheels, copies checkpoint manifests into the
vendored TRIDENT package, and records `profile=hpc-for-health` in
`adapter-state.json`. Subsequent CLI calls read that state to resolve asset
paths.

To view the resolved environment values after setup, run:

```bash
wsi-trident-adapter profile show
```

No module loads are required because the profile assumes the cluster image
already provides CUDA, OpenSlide, and supporting libraries.

## 5. Run the bundled example

Because the example assets live under `/cluster/projects/kumargroup`, they are
accessible only from data nodes (e.g., `h4huhndata1`). Request a small
allocation and run the fetch there:

```bash
salloc -t 1:00:00 -c 1 --mem=4G
# inside the allocation
wsi-trident-adapter example fetch --dest ~/wsi-trident-adapter/example
```

Check that the copied directory inherits `750/640` permissions and contains
sample slides plus `config.yaml`.

## 6. Submit a test job

The example bundle already includes `run.sh`. Edit that file to point its
`source /path/to/.venv/bin/activate` line at your virtual environment. If you
followed this guide, the correct path is `source ../.venv/bin/activate`.
Submit the job:

```bash
sbatch run.sh
```

Monitor with `squeue` and inspect logs under `out/`.

## Operational notes

-   Avoid issuing repeated CLI commands on `h4huhnlogin1`; the tools spawn Python
    processes and can burden the shared login node.
-   Use `salloc` or job submissions for any workflow that might take longer than
    a few seconds or touches shared storage under `/cluster/projects`.
