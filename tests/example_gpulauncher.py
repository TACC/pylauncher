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
## Emulate the classic launcher, using a one liner
##

example = "GPULauncher"
try :
    gpuspernode=os.environ['GPUSPERNODE']
except:
    gpuspernode=1

pylauncher.GPULauncher\
    ("gpucommandlines",gpuspernode=gpuspernode,
     # optional spec of output dir:
     workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
     debug="ssh+host+exec+job")

