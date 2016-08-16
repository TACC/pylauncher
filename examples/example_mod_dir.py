#!/usr/bin/env python

import pylauncher

##
## Emulate the classic launcher, using a one liner
##

pylauncher.ClassicLauncher("modcommandlines",debug="job+host+task+exec+ssh")
#pylauncher.ClassicLauncher("commandlines")

