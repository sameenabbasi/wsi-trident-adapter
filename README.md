# wsi-trident-adapter

Lightweight tooling that wraps TRIDENT for offline HPC clusters and local environments.

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
