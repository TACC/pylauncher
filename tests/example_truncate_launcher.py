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
## Classic launcher with a per-task timeout
##

example = "TruncateLauncher"
pylauncher.ClassicLauncher(
    "commandlines",
     # optional spec of output dir:
     workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
    taskmaxruntime=30,delay=1,debug="job+host")

