# WSI Trident Adapter

Adapter layer around [TRIDENT](https://github.com/mahmoodlab/TRIDENT) that provides a stable CLI for offline and cluster workloads. Use this README for the current development workflow while we stabilise the package.

---

## Prerequisites

- Python 3.9+
- Access to the private repository (`git@github.com:haydenych/wsi-trident-adapter.git`)
- A virtual environment with the CUDA/OpenSlide stack required by your target cluster (load the modules before installing if needed)

---

## Install (development branch)

```bash
# activate your virtual environment first
pip install --upgrade pip
pip install "git+ssh://git@github.com/haydenych/wsi-trident-adapter.git@dev"
```

Installing exposes two console scripts:

- `wsi-trident-adapter-install` – copies profile assets (checkpoints, wheels, requirements) into your environment
- `wsi-trident-adapter` – runs the adapter CLI around TRIDENT

---

## Configure the environment

Run the profile installer once per virtual environment. Pick the profile that matches your cluster; `hpc-for-health` is the current default.

```bash
wsi-trident-adapter-install hpc-for-health
```

The command copies checkpoint manifests into the vendored TRIDENT modules and installs any profile-specific wheels listed in `trident_adapter/profiles/<profile>/requirements.txt`.

---

## Sanity check the CLI

```bash
wsi-trident-adapter --help
```

You should see the `extract` subcommand along with the core options `--config`, `--task`, `--wsi-dir`, and `--output-dir`.

---

## Run a quick example

The repository bundles a simple configuration and slides under `example/`. After installing the profile:

```bash
sbatch example/run_hpc4health.sh 
```

Inspect `example/out/` for generated contours, patches, and HDF5 features. Adjust `example/config.yaml` or create your own from `configs/config_template.yaml` for real data.