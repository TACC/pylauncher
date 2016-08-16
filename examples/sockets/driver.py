##
## Driver program generating commandlines
## and sending them over a socket to the server
##
import random
import socket
import sys

import pylauncher

HOST = 'localhost'    # The remote host
PORT = 5007              # The same port as used by the server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))
ntasks = 20
nack = 0; ndone = 0
for data in [ "sleep %d; echo foo%d" % ( int(4*random.random()),i )
              for i in range(ntasks)]:
    s.send(data)
    return_data = s.recv(1024)
    if return_data=="ACK":
        print "ack"
        nack += 1
    else:
        ndone += 1
        taskid,outfile = return_data.split(";")
        print taskid,outfile
print "submitted",ntasks,"; returned",ndone

if nack+ndone!=ntasks:
    print "#ack=",nack,"; #done=",ndone
    sys.exit(1)

for rem in range(ntasks):
    return_data = s.recv(1024)
    if return_data=="ACK":
        print "missing ack just came in"
        nack += 1
    else:
        ndone += 1
        taskid,outfile = return_data.split(";")
        print taskid,outfile

# for count in range(2*ntasks):
#     return_data = s.recv(1024)
#     if return_data=="ACK":
#         nack += 1
#     else:
#         taskid,outfile = return_data.split(";")
#         print taskid,outfile
s.close()
