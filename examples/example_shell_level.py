#!/usr/bin/env python

import pylauncher
import re
import os

##
## This is a very simple example with fake commands and fake jobs
##

# write a function that coughs up commandlines
commandfile = open("commandlines")
def commandgenerator():
    for line in commandfile.readlines():
        if re.match('^ *#',line) or re.match('^ *$',line):
            continue # skip blank and comment
        yield line.strip(),20
    yield "stop",0

# tools to recognize when a job has ended
def commandwrap(task,line):
    stamp = pylauncher.defaultExpireStamp(task.id)
    command = " ( %s ; echo \"expiring %s\"; touch %s ) & " \
              % (line,str(task.id),task.expireStamp)
    print "Creating:\n" + command
    return command

# user has to write an event loop
npool = 100
job = pylauncher.Job(nhosts=npool,commandgenerator=commandgenerator,
                     commandwrap=commandwrap,delay=2.)
#job.crashtick = 40 ## simulate crash
while True:
    state = job.tick() # delay, recognize expiries, start new jobs
    print "\nCurrent state:",state
    if state is not None:
        if re.match('^expired',state):
            # post processing of expired jobs
            id = state.split()[1] 
            print "Processing expired task "+id
        elif re.match('^finished',state):
            break
