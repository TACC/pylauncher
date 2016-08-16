#!/usr/bin/env python

import MySQLdb
import time
import random
import sys

if len(sys.argv)<3:
    raise Exception("Need two commandline arguments")

try:
    rc = open(".dbrc")
except:
    print "could not find database rc file"; sys.exit(1)
rclines = rc.readlines(); rc.close()

if len(rclines)<1:
    raise Exception("malformed rc file")
try:
    db = MySQLdb.connect(host="dbhost.utexas.edu",\
                             user="dbuser",\
                             passwd=rclines[0].strip(),\
                             db="dttable")
except:
    print "\nCould not connect to the database"; sys.exit(1)
c = db.cursor()

command = "insert into launchtable (`key`,`value`) values (%s,%s)" % \
    (sys.argv[1],sys.argv[2])
print command
c.execute( command )

c.close()
db.close()

time.sleep( int( 15*random.random() ) )
