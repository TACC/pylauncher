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
################################################################

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

from pylauncher import pylauncher as launcher
launcher.ClassicLauncher("directorycommandlines",debug="host+job+exec")

