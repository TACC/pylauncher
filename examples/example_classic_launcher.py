#!/usr/bin/env python

import pylauncher3

##
## Emulate the classic launcher, using a one liner
##

#pylauncher.ClassicLauncher("corecommandlines",debug="job+host+task")
pylauncher3.ClassicLauncher("commandlines",debug="job")

