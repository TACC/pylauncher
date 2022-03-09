################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2022
#### eijkhout@tacc.utexas.edu
####
#### https://github.com/TACC/pylauncher
####
################################################################

import sys

if len(sys.argv)<2:
    print("Usage: make_parallel_lines n [p: default 4]")
    sys.exit(1)

n = int(sys.argv[1])
if len(sys.argv)==3:
    p = int(sys.argv[2])
else: p = 4
slp = 30

f = open("parallellines","w")
for l in range(0,int(n/p)):
    f.write("%d,./parallel %d %d\n" % (p,l,slp))
f.close()
