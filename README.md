# Guide for the 3d extinction map

## Installing

Please read this section entirely before cloning.

### Requirements

To be able to clone the repository you need to install two pieces of software: [git](https://git-scm.com/) and the [git-lfs](https://git-lfs.github.com/) extension. Both can be installed using your system's package manager, if this is not possible you can download and install them manually from their respective websites, linked above.

The reason for using git-LFS comes from limits imposed on large files, such as those containing the 3d extinction maps.

The requirements for the code are:

- astropy
- [dustmaps](https://github.com/gregreen/dustmaps)
- healpy
- matplotlib
- [mwdust](https://github.com/jobovy/mwdust)
- numpy

### Install option 1: download everything

Open a terminal, navigate to a folder of your choice and run

```bash
git clone https://github.com/willclarkson/rubinCadenceScratchWIC.git
```

or, if you set up SSH keys for your GitHub account,

```bash
git clone git@github.com:willclarkson/rubinCadenceScratchWIC.git
```

This will create a new folder named `rubinCadenceScratchWIC` and download **all** the files of the repository inside. Please note that you need at least 1GB free.

### Install option 2: download without heavy files

If you do not want to download the largest files, you have to run the following commands **before** cloning the repository:

```bash
git config --global filter.lfs.smudge "git-lfs smudge --skip -- %f"
git config --global filter.lfs.process "git-lfs filter-process --skip"
```

After that you can use one of the commands shown in "Option 1". The heavy, LFS tracked files will not be downloaded.

If you do not want to change the global Git settings, remove the `--global` argument form the two commands above.

To revert these changes you can run

```bash
git config --global filter.lfs.smudge "git-lfs smudge -- %f"
git config --global filter.lfs.process "git-lfs filter-process"
```

and remember to remove the `--global` argument if you changed only the local Git configuration before.

If you do not want to change the Git configuration you can also run 

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/willclarkson/rubinCadenceScratchWIC.git
```

or 

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone git@github.com:willclarkson/rubinCadenceScratchWIC.git
```

You should be aware, however, that not changing the Git configuration means that if you perform a `git checkout`, all files will be downloaded.

### Speeding up the download

If you have the required disk space and your internet connection is good, you can replace `git clone` with `git lfs clone` to take advantage of parallel downloads for the large files and complete the clone faster.

### Using the `gitlfs` branch

Currently (May 14, 2021) the maps are only working with the `gitlfs` branch, therefore after cloning you will have to run

```bash
git checkout gitlfs
```

from inside the repository's folder on your disk.

### Downloading the large files

If you opted for cloning without the large files, you will eventually have to download one or more map files. To download a single file, then run

```bash
git lfs pull --include "filename"
```

To get a list of LFS-tracked files, you can either see what lies inside the `extmaps` folder on the [github page](https://github.com/willclarkson/rubinCadenceScratchWIC/tree/gitlfs/extmaps) or run

```bash
git lfs ls-files --all
```

that will return all the available files.

If at some point you want to download *all* the heavy files, just run

```bash
git lfs pull
```

and remember that you need about 1GB of free disk space for all of the files.

## Preparing the maps

The maps are downloaded in a compressed format. To use them, you first need to decompress them. Please be aware that the uncompressed files will take, in total, about 4GB.
To decompress every map, run the following from the terminal, from inside the repository folder:

```bash
gzip -dk extmaps/*.gz
```

or, alternatively, you can run

```bash
gunzip -k extmaps/*.gz
```

If you want to decompress only one file to save space on the disk just replace `*.gz` with the name of the file you need.

The `-k` flag tells the programs to keep the compressed files after the decompression. If you want to save space on your disk, just leave that flat out (but leave the `-d` flag if you are using `gzip`).

