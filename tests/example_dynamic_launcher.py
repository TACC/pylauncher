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
import random
import time
import pylauncher

# set debug mode
debug="host+job+command+exec"
#debug=""

#
# create dynamic launcher job
#
job = pylauncher.DynamicLauncher(
     workdir=f"pylauncher_tmp_dynamic_{ os.environ['SLURM_JOBID'] }",
    debug=debug,cores=12 )

#
# command generation and execution loop
#
icmd = 0
job.starttime = time.time()
while True:
    icmd = icmd+1
    if icmd<=15:
        #
        # generate and append commandlines
        #
        cmdline = "sleep "+str( random.randint(10,icmd+10) )
        job.append( cmdline )
    elif icmd==20:
        #
        # declare that there will be no more commandlines
        #
        job.finish()
    #
    # print intermediate job statistics
    #
    print( f"Cycle {job.tock}:\n{str(job.queue)}" )
    #
    # make progress
    #
    job.tick()
    #
    # exit when all tasks finished
    #
    if job.finished():
        print( f"dynamic job break" )
        break
#
# clean up: release ssh connections
#
job.hostpool.release()
#
# final statistics
#
print(job.final_report())
