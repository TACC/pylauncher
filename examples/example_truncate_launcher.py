#!/usr/bin/env python

import pylauncher3

##
## Classic launcher with a per-task timeout
##

pylauncher3.ClassicLauncher("commandlines",taskmaxruntime=30,delay=1,debug="job+host")

