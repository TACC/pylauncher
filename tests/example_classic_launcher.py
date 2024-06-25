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
import pylauncher

##
## Emulate the classic launcher, using a one liner
##

pylauncher.ClassicLauncher\
    ("commandlines",
     # optional spec of output dir:
     # workdir=f"pylauncher_out{os.environ['SLURM_JOBID']}",
     debug="ssh+host+exec+task+job")
