#!/usr/bin/env python

import pylauncher

##
## Emulate the classic launcher, using a one liner
##

#pylauncher.ClassicLauncher("corecommandlines",debug="job+host+task")
pylauncher.ClassicLauncher("commandlines",debug="job")

