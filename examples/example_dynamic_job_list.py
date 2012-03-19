#!/usr/bin/env python

import pylauncher
import random

##
## Extend the classic launcher 
## by making the commandline generator dynamic,
## keep the event loop internal
##

# object that coughs up commandlines and processes
# expired jobs
class joblist():
    def __init__(self,list):
        self.list = list; self.njobs = len(self.list)
    def generate(self):
        if self.njobs<30:
            if len(self.list)>0:
                j = self.list.pop(); self.njobs += 1
                return j,1
            else:
                return "stall",1
        return "stop",1
    def expire(self,id):
        print "Processing expired task ",id
        self.list.append("sleep "+str(10+int(30*random.random())))

#
# we create a dynamic launcher job to that will create new commands
# while running
#
job = pylauncher.DynamicLauncher(
    joblist(
        [ "sleep "+str(10+int(30*random.random())) for i in range(10) ]
    )
    )
