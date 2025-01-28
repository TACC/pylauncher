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
import pylauncher as launcher

##
## Emulate the classic launcher, using a one liner
##

launcher.SubmitLauncher\
    ("commandlines",
     "-A A-ccsc -N 1 -n 1 -p small -t 0:5:0", # slurm arguments
     nactive=2, # two jobs simultaneously
     maxruntime=300,
     # optional spec of output dir:
     workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
     debug="host+queue+exec+job+task")

