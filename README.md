# wsi-trident-adapter

Lightweight tooling that wraps [TRIDENT](https://github.com/mahmoodlab/TRIDENT) for offline HPC 
clusters and local environments. TRIDENT provides the core segmentation/patching/feature pipeline; this 
adapter focuses on HPC packaging and reproducibility.

## Profiles

- `hpc-for-health`
- `compute-canada` (TBD)

## Why use this adapter?

- **Offline-friendly asset management:** the adapter keeps large checkpoints on
  shared storage and wires environment variables automatically.
- **Profile-aware scripts:** each profile ships ready-made SLURM templates,
  module lists, and example pipelines tailored to its cluster.
- **Stable CLI wrapper:** commands such as `profile`, `config`, `example`, and
  `run` expose repeatable workflows, insulating you from TRIDENT API changes.

## Updating

Because the adapter is installed directly from Git tags (not PyPI), `pip install -U` only fetches a new version when you specify a newer tag explicitly.
To upgrade, re-run 
```bash
pip install -U "git+https://github.com/haydenych/wsi-trident-adapter.git@vX.Y.Z"
```
after replacing `vX.Y.Z` with the desired release, and then rerun
```bash
wsi-trident-adapter-install setup <profile>
```
so the active profile and checkpoints stay in sync.

### Can you run TRIDENT directly?

**Yes and no.** TRIDENT remains the underlying engine, so you can still drive it
directly. On clusters without internet access (e.g., HPC4Health), you would
otherwise need to:

- download checkpoints elsewhere  
- place them in an accessible location (e.g., XDG-cache directory, shared project
  storage, or your own custom path)  
- pass the weights path into TRIDENT or configure its cache manually  
- manage module stacks  
- hand-write SLURM scripts  

The adapter automates these chores with profile-aware commands, consistent asset
locations, and SLURM templates—so you can focus on the pipeline itself rather
than infrastructure details.

On sites with internet access (e.g., many Compute Canada environments), you *can*
run TRIDENT directly. However, the adapter still provides a known-good setup,
consistent directory layout, and reproducible job templates so teams can
standardise their workflow.

---

Installation, quick start instructions, and environment-specific guides (run output 
structure, rerun guidance, etc.) live in [`docs/`](docs/).

# Notice: Version 0.1.0 (Legacy Release)

The v0.1.0 release of **wsi-trident-adapter** is now deprecated.

Version **0.2.0** introduces a complete redesign of the adapter structure, 
including new CLI entry points, reorganized modules (`core/`, `utils/`), and 
profile-specific installation flows.

Known issues in v0.1.0 — including incomplete ResNet-50 feature extraction, 
path resolution errors, and missing HPC environment profiles — will **not** be 
fixed in this branch.

Please upgrade to the latest stable release:

```bash
pip install "git+https://github.com/haydenych/wsi-trident-adapter.git@v0.2.0"