import sys

if len(sys.argv)<2:
    print "Usage: make_parallel_lines n [p: default 4]"

n = int(sys.argv[1])
if len(sys.argv)==3:
    p = int(sys.argv[2])
else: p = 4
slp = 30

f = open("parallellines","w")
for l in range(0,n/p):
    f.write("%d,./parallel %d %d\n" % (p,l,slp))
f.close()
