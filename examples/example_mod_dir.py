#!/usr/bin/env python

import pylauncher3

##
## Emulate the classic launcher, using a one liner
##

pylauncher3.ClassicLauncher("modcommandlines",debug="job+host+task+exec+ssh")
#pylauncher3.ClassicLauncher("commandlines")

