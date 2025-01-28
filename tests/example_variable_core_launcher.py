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

import pylauncher

##
## Emulate the classic launcher, using a one liner
##

example = "VariableCoreLauncher"
pylauncher.ClassicLauncher(
    "corecommandlines",
     # optional spec of output dir:
     workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
    debug="job+task+host+exec+command",
    cores="file",
)

