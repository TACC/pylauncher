#!/usr/bin/env python
################################################################
####
#### Example of the pylauncher with MPI jobs.
####
################################################################

import pylauncher3

##
## spawn a bunch of MPI parallel jobs, with a core count
## that is constant, specified here.
##
pylauncher3.IbrunLauncher("parallellines",cores=3,
                         debug="job+host+task+exec")
