# WSI-Pipeline

## Setup (HPC4Health)

```
git clone git@github.com:haydenych/WSI-Pipeline.git

module load python3/3.10.9
cd WSI-Pipeline
git submodule update --init --recursive
python3.10 -m venv .venv && source .venv/bin/activate
pip3 install --upgrade pip
pip3 install .[all]
```

## Setup (Compute Canada)

Not yet supported

## How to use the tool?

### Step 1: Preparing the config file

-   Create a copy of [configs/config_template.yaml](configs/config_template.yaml).
-   Change `io.wsi_dir` to your slide images directory. Make sure this path links directly to the slide images but not sub-folders containing the images.
-   Change `io.job_dir` to your output location.
-   For first time users, you may also want to change `patching.magnification` and `patching.patch_size`, while leaving the rest untouched.
-   Refer to the [config instructions manuals](configs/config_instructions.md) for detailed usage of each configuration.

### Step 2: Preparing the run script

-   Create a copy of [scripts/\*\*/run_template.sh](scripts/hpc4health/run_template.sh).
-   Change variables marked with **TODO**.
-   For **TODOs** in sbatch, you can simply delete the line if you do not want them. You can also replace the whole slurm section if you wish. Please refer to the [sbatch guide](https://slurm.schedmd.com/sbatch.html) for detailed usage.
-   If you simply want to extract features, use `TASK="all"`. If you are cautious and want some extra quality control, use `TASK="seg"` to check the segmentation contours. Then proceed with patching `TASK="patch"` and feature extraction `TASK="feat"`.

-   **Reminder**: Do not add any space bars between vairiable assignments in a bash script. i.e. `TASK = "all"` will cause you an [error](https://stackoverflow.com/a/41748518) :)

### Step 3: Run the bash script

```
sbatch scripts/hpc4health/run.sh
```

## Common Errors / FAQ

Q: I cannot git clone this repository.

A: Since this is a private repository, you'll have to set up a [ssh key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent) to clone this repo.