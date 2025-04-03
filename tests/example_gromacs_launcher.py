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
#### Example of the pylauncher with Gromacs
####
################################################################

import os
import sys
import pylauncher

try :
    gmx = os.environ['TACC_GROMACS_BIN']
except:
    print( "Make sure to load the gromacs module" )
    sys.exit(1)

##
## spawn a bunch of MPI parallel jobs, with a core count
## that is constant, specified here.
##
example = "GromacsMPILauncher"
pylauncher.IbrunLauncher("gromacslines",cores=24,
     # optional spec of output dir:
     workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
                         debug="job+host+task+exec")
