#!/usr/bin/env python

import pylauncher3

##
## Launcher multi-core jobs, but with large core counts.
## this will leave many processor cores unused.
##

pylauncher3.ClassicLauncher("bigcorecommandlines",
                            debug="job+task+host",
                            cores="file")

