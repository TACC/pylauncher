#!/usr/bin/env python

import pylauncher3

##
## spawn a bunch of MPI parallel jobs, with a core count
## that is specified in the file
##
pylauncher3.IbrunLauncher("parallellinescores",cores="file",
                         debug="job+host+task+exec")
