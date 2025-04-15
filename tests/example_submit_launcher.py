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

import os
import shutil

import pylauncher

try:
    jobid = os.environ['SLURM_JOBID']
    raise Exception("This example should be run outisde of SLURm")
except:
    pass

##
## Emulate the classic launcher, using a one liner
##

#
# what is the project you are charging against?
#
TACCproject = "A-ccsc" # this only works for Victor. Customize!

#
# deduce a queue, or override
#
system=os.environ['TACC_SYSTEM']
if system=="stampede3":
    queue="skx"
else: queue="small"

#
# how many jobs can be in the queue?
# read the userguide: if you go over this, jobs get lost
#
maxjobs = 2

#
# declare working dir, and delete if already there
#
example = "SubmitLauncher"
workdir = f"pylauncher_tmp_{example}"
shutil.rmtree(workdir,ignore_errors=True)

pylauncher.SubmitLauncher\
    ("submitlines",
     f"-A {TACCproject} -N 1 -n 1 -p {queue} -t 0:5:0", # slurm arguments
     nactive=maxjobs,      # two jobs simultaneously
     ## maxruntime=900,       # this test should not take too long
     workdir=workdir,
     debug="host+queue+exec+job+task", # lots of debug output
     )

