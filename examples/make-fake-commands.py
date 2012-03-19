#!/usr/bin/env python

import random

ncommands = 50 # make this many fake commands in a text file, one per line

f = open("commandlines","w")
for c in range(ncommands):
    f.write("echo \"command "+str(c)+"\"; sleep "+str(10+int(20*random.random()))+"\n")

f.close()
