#!/usr/bin/env python
################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2022
#### eijkhout@tacc.utexas.edu
####
#### https://github.com/TACC/pylauncher
####
################################################################

from pylauncher import pylauncher as launcher

##
## Launcher multi-core jobs, but with large core counts.
## this will leave many processor cores unused.
##

launcher.ClassicLauncher("bigcorecommandlines",
                            debug="job+task+host",
                            cores="file")

