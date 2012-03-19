#!/usr/bin/env python

import pylauncher
import random
import re
import os
import time

##
## Extend the classic launcher 
## by making the number of cores per job variable
##

njobs = 0
# set up initial jobs
joblist = [ "sleep "+str(10+int(30*random.random())) for i in range(10) ]
# function that coughs up commandlines;
# note that the event loop can append jobs to the job list
def jobgenerator():
    global joblist,njobs
    while njobs<30:
        if len(joblist)>0:
            j = joblist.pop(); njobs += 1
            ncores = int(1+5*random.random()) # number 1..6
            yield j,ncores
        else:
            yield "stall",1
    yield "stop",1

#
# we create a parallel launcher job to execute the commands
# in the file "commandlines"
#
os.system("rm -rf .launcher ; mkdir .launcher")
job = pylauncher.Job(
    hostlist=pylauncher.launchergetpehosts(),
    commandgenerator=jobgenerator,
    commandwrap=pylauncher.launchercommandwrap,
    completionTest=pylauncher.launchercompletionTest,
    commandprefixer=pylauncher.launcheribrunner)

#
# the user has to write an event loop
#
while True:
    state = job.tick() # delay, recognize expiries, start new jobs
    if state is not None:
        if re.match('^expired',state):
            # post processing of expired jobs
            id = state.split()[1] 
            print "Processing expired task "+id
            # as a result of post-processing, a new job is generated
            joblist.append("sleep "+str(10+int(30*random.random())))
        elif re.match('^finished',state):
            break
