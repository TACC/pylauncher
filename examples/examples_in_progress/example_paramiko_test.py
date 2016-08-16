#!/usr/bin/env python

import pylauncher

##
## test our ssh routines
##

pylauncher.ClassicLauncher("modcommandlines",debug="job+host+task+exec+ssh")
#pylauncher.ClassicLauncher("commandlines")

