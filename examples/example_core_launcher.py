#!/usr/bin/env python

import pylauncher3

##
## Emulate the classic launcher, using a one liner
##

pylauncher3.ClassicLauncher("commandlines",
                            cores=4,
                            debug="job+host+exec",
                            )
