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

workdir = f"{os.environ['SCRATCH']}/pylauncher_out{os.environ['SLURM_JOBID']}"
print( f"Using workdir: <<{workdir}>>" )

pylauncher.ClassicLauncher\
    ("commandlines",
     # optional spec of output dir:
     workdir=workdir,
     debug="host+exec+task+job")
