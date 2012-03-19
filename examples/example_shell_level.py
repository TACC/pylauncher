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
os.system("rm -rf .launcher ; mkdir .launcher")
def expirestamp(id):
    return "expire"+str(id)
def commandwrap(task,line):
    stamp = expirestamp(task.id)
    command = " ( "+line+"; echo \"expiring "+str(task.id)+"\"; touch .launcher/"+stamp+" ) & "
    print "Creating:\n" + command
    return command
def completionTest(task):
    return os.path.isfile(os.getcwd()+"/.launcher/"+expirestamp(task.id))

# user has to write an event loop
npool = 100
job = pylauncher.Job(nhosts=npool,commandgenerator=commandgenerator,
                   commandwrap=commandwrap,completionTest=completionTest)
job.crashtick = 40 ## simulate crash
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
