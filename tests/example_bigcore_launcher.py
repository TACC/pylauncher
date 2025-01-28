#!/usr/bin/env python
################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2025
#### eijkhout@tacc.utexas.edu
####
#### https://github.com/TACC/pylauncher
####
################################################################

import os
import pylauncher

##
## Launcher multi-core jobs, but with large core counts.
## this will leave many processor cores unused.
##

example = "BigCoreLauncher"
pylauncher.ClassicLauncher(
    "bigcorecommandlines",
     workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
    debug="job+task+host",
    cores="file")

