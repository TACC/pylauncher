#!/usr/bin/env python3

docstring = """
paramiko_test.py

Copyright 2026 Victor Eijkhout

A short test program of the paramiko python library.

Usage:
  ./paramiko_test.py somehost.tacc.utexas.edu

1. Allocate a node and run this on the node to itself
2. Allocate a node and run this from the login node to the compute
3. Allocate two compute nodes and test the one from the other.
"""

import sys
if len(sys.argv)<2:
    print( f"Usage: {sys.argv[0]} hostname" )
    print( docstring )
    sys.exit(1)

try:
    import paramiko
except:
    print("""
Your python is missing the paramiko module.
Please do: pip install paramiko
on the Unix commandline.
This run will now quit.
""")
    sys.exit(0)

def ssh_client_test(host):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print( f"Create paramiko ssh client to {host}",flush=True)
    ssh.connect(host)
    cmdline = "hostname"
    print( f" .. done, now executing <<{cmdline}>>" )
    _,stdout,_ = ssh.exec_command( cmdline )
    result = stdout.readline().strip('\n')
    print( f" .. result: <<{result}>>" )
    print( "closing...." )
    ssh.close()
    print( " .. that's all fffffolks" )

ssh_client_test( sys.argv[1] )
