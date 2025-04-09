# WSI-Pipeline


## Setup (HPC4Health)
```
git clone git@github.com:haydenych/WSI-Pipeline.git

module load python3/3.10.9
cd WSI-Pipeline && python3.10 -m venv .venv
source .venv/bin/activate
pip3 install .[all]
```

Since this is a private repository, you'll have to set up a [ssh key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent) to clone this repo.

## Setup (Compute Canada)
Not yet supported