#!/usr/bin/env python

import random

ncommands = 300 # make this many fake commands in a text file, one per line
maxtime = 30
mintime = 10

f = open("commandlines","w")
f.write("#\n# Automatically generated commandlines\n#\n")
for c in range(ncommands):
    if 10*int(c/10)==c and c>0:
        f.write(" \n")
    f.write("echo \"command "+str(c)+"\"; sleep "+str(mintime+int((maxtime-mintime)*random.random()))+"\n")
f.close()
