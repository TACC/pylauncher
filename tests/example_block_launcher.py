#!/usr/bin/env python
################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2026
#### eijkhout@tacc.utexas.edu
####
#### https://github.com/TACC/pylauncher
####
################################################################

import os
import pylauncher

##
## Emulate the classic launcher, using a one liner
##

example = "ClassicLauncher"
pylauncher.ClassicLauncher\
    ("blockcommandlines",
     # optional spec of output dir:
     workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
     schedule="block3",
     debug="host+exec+task+job+cmd")
