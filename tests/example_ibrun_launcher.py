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
#### Example of the pylauncher with MPI jobs.
####
################################################################

import pylauncher

##
## spawn a bunch of MPI parallel jobs, with a core count
## that is constant, specified here.
##
pylauncher.IbrunLauncher("parallellines",cores=3,
                         debug="job+host+task+exec")
