#!/usr/bin/env python

import pylauncher
import random
import re
import os
import time

##
## Classic launcher with saving of state
## run this example at least twice.
##

njobs = 0
# set up initial jobs
joblist = [ "sleep "+str(10+int(30*random.random())) for i in range(30) ]

# function that coughs up commandlines;
# note that the event loop can append jobs to the job list
def jobgenerator():
    global joblist,njobs
    qfile = os.curdir+"/queuestate"
    if os.path.exists(qfile):
        print "reissuing commands from terminated run"
        qfile = open(qfile,"r")
        for line in qfile.readlines():
            line = line.strip()
            if line=="completed": break
            if line in ["queued","running"]: continue
            yield line,1
    while njobs<300:
        if len(joblist)>0:
            j = joblist[0]; joblist = joblist[1:]; njobs += 1
            yield j,1
        else:
            yield "stall",1
    yield "stop",1

#
# we create a parallel launcher job to execute the commands
# in the file "commandlines"
#
os.system("rm -rf .launcher ; mkdir .launcher")
job = pylauncher.LauncherJob(
    commandgenerator=jobgenerator)

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
