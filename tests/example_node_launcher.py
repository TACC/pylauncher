#!/usr/bin/env python
################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2025
#### eijkhout@tacc.utexas.edu
####
#### pylauncher example: launcher one multi-threaded job per node
####
################################################################

import os
import pylauncher

##
## Emulate the classic launcher, using a one liner
##

example = "NodeLauncher"
pylauncher.ClassicLauncher\
    ("nodecommandlines",
     # optional spec of output dir:
     workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
     cores="node",
     debug="job+host+exec",
    )
