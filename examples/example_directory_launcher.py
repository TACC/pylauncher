#!/usr/bin/env python

##
## make a file of commandlines, tuned to the current run
##
import os
nprocs = os.environ['SLURM_NPROCS']
nprocs = int(nprocs)
with open("directorycommandlines","w") as commandfile:
    for count in range(nprocs):
        commandfile.write("mkdir out-PYL_ID ; cd out-PYL_ID ; ../randomaction PYL_IC > output\n")
    
##
## Emulate the classic launcher, using a one liner
##

import pylauncher3
pylauncher3.ClassicLauncher("directorycommandlines",debug="host+job+exec")

