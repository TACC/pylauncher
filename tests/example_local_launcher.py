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

from pylauncher

##
## Execute locally
## -- you need to specify the number of cores you have.
## -- this assumes that process placement is done sensibly.
##

ncores = 24
example = "LocalLauncher"
pylauncher.LocalLauncher(
    "commandlines",
     # optional spec of output dir:
     workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
    ncores,debug="job") # debug="job+host+task")

