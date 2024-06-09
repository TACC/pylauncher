#!/usr/bin/env python
################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2024
#### eijkhout@tacc.utexas.edu
####
#### https://github.com/TACC/pylauncher
####
################################################################

import os
import pylauncher as launcher

##
## Emulate the classic launcher, using a one liner
##

launcher.GPULauncher\
    ("gpucommandlines",
     # optional spec of output dir:
     # workdir=f"pylauncher_out{os.environ['SLURM_JOBID']}",
     debug="ssh+host+exec+job")

