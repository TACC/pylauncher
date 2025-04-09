#!/usr/bin/env python
################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2025
#### eijkhout@tacc.utexas.edu
####
#### this tests our correct interpretation of commas in the commandlines
####
################################################################

import os
import pylauncher

##
## Emulate the classic launcher, using a one liner
##

example = "CommaLauncher"
pylauncher.ClassicLauncher(
    "commalines",
    # optional spec of output dir:
    workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
    debug="host+jobs+exec")
