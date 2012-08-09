#!/usr/bin/env python

import os
import random

ncommands = 1000 # make this many fake commands in a text file, one per line
maxtime = 30
mintime = 10
cwd = os.getcwd()

f = open("hellolines","w")
f.write("#\n# Automatically generated commandlines\n#\n")
for c in range(ncommands):
    if 10*int(c/10)==c and c>0:
        f.write(" \n")
    f.write("source %s/hello.sh %s %s\n" % \
            (",",
             c,
             mintime+int((maxtime-mintime)*random.random())) )
#     f.write("echo \"command %s\"; sleep %d; %s/hello %d\n" % \
#             ( str(c),
#               mintime+int((maxtime-mintime)*random.random()),
#               "/share/home/00434/eijkhout/Projects/pylauncher",
#               c) )
f.close()
