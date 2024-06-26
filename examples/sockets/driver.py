##
## Driver program generating commandlines
## and sending them over a socket to the server
##
import os
import random
import socket
import subprocess
import sys

import pylauncher

HOST = '127.0.0.1'
PORT = 5007              # The same port as used by the server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))
ntasks = 20
nack = 0; ndone = 0

for idata,data in enumerate\
        ( [ "sleep %d; echo foo%d" % ( 5+int(4*random.random()),i ) for i in range(ntasks)] ):
    s.send(data.encode())
    return_data = s.recv(1024).decode()
    if return_data=="ACK":
        print( f"[1] ack on task {idata}" )
        nack += 1
    else:
        ndone += 1
        taskid,outfile = return_data.split(";")
        print( f"[1] task {taskid} finished with results in {outfile}" )
print("submitted",ntasks,"; returned",ndone)

if nack+ndone!=ntasks:
    print("#ack=",nack,"; #done=",ndone)
    sys.exit(1)
else:
    print("All tasks done")
    sys.exit(0)
    s.close()

for rem in range(ntasks):
    return_data = s.recv(1024)
    if return_data=="ACK":
        # I don't think this can happen
        print("missing ack just came in")
        nack += 1
    else:
        ndone += 1
        taskid,outfile = return_data.split(";")
        print(f"[2] task {taskid} finished with results in {outfile}")

# for count in range(2*ntasks):
#     return_data = s.recv(1024)
#     if return_data=="ACK":
#         nack += 1
#     else:
#         taskid,outfile = return_data.split(";")
#         print(taskid,outfile)
