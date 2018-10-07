#!/usr/bin/env python

import pylauncher3

##
## Emulate the classic launcher, using a one liner
##

pylauncher3.ClassicLauncher("corecommandlines",
                           debug="job+task+host+exec+command",
                           cores="file",
                           )

