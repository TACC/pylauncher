#!/usr/bin/env python
################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2022
#### eijkhout@tacc.utexas.edu
####
#### https://github.com/TACC/pylauncher
####
#### Example of the pylauncher with MPI jobs.
####
################################################################

from pylauncher import pylauncher as launcher

##
## spawn a bunch of MPI parallel jobs, with a core count
## that is constant, specified here.
##
launcher.IbrunLauncher("parallellines",cores=3,
                         debug="job+host+task+exec")
