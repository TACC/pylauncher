#!/usr/bin/env python

import pylauncher
import random
import re
import os

##
## Emulate the classic launcher, the hard way
##

# write a function that coughs up commandlines
commandfile = open("commandlines")
def commandgenerator():
    for line in commandfile.readlines():
        yield line.strip(),1
    yield "stop",0

# tools to recognize when a job has ended
os.system("rm -rf .launcher ; mkdir .launcher")
def expirestamp(id):
    return "expire"+str(id)
def commandwrap(task,line):
    id = task.id
    stamp = os.getcwd()+"/.launcher/"+expirestamp(id)
    xfile = os.getcwd()+"/.launcher/exec"+str(id)
    x = open(xfile,"w")
    x.write(line+" # the actual command\n")
    x.write("echo \"expiring "+str(id)+"\" # just a trace message\n")
    x.write("touch "+stamp+" # let the event loop know that the job is finished\n")
    x.close()
    print "Creating:\n" + line
    return "source "+xfile
def ssher(task,line,hostpool,poolsize):
    return "ssh "+hostpool['nodes'][0]+" "+line+" &"
def completionTest(task):
    id = task.id
    return os.path.isfile(os.getcwd()+"/.launcher/"+expirestamp(id))

# user has to write an event loop
hostfile = os.environ["PE_HOSTFILE"]
hostfile = open(hostfile,"r")
hostlist = []
for h in hostfile.readlines():
    line =h.strip(); line = line.split(); host = line[0]; n = line[1]
    for i in range(int(n)):
        hostlist.append(host)
job = pylauncher.Job(
    hostlist=hostlist,commandgenerator=commandgenerator,
    commandwrap=commandwrap,
    completionTest=completionTest,
    commandprefixer=ssher)
while True:
    state = job.tick() # delay, recognize expiries, start new jobs
    if state is not None:
        if re.match('^expired',state):
            # post processing of expired jobs
            id = state.split()[1] 
            print "Processing expired task "+id
        elif re.match('^finished',state):
            break
