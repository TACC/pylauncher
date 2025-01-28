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
from pylauncher import pylauncher as launcher

##
## Emulate the classic launcher, using a one liner
##

launcher.ClassicLauncher(
    "barriercommandlines",
    workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
    debug="job")

