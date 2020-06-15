#!/usr/bin/env python

import pylauncher3

##
## Execute locally
## -- you need to specify the number of cores you have.
## -- this assumes that process placement is done sensibly.
##

ncores = 24
pylauncher3.LocalLauncher("commandlines",ncores,debug="job") # debug="job+host+task")

