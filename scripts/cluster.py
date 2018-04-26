#!/usr/bin/env python

from pylauncher import *

print "Detecting cluster name:",ClusterName()

print "Host list",HostListByName()

pool = DefaultHostPool()
print "Default pool has %d cores" % len(pool)
