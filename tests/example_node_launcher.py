#!/usr/bin/env python
################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2024
#### eijkhout@tacc.utexas.edu
####
#### pylauncher example: launcher one multi-threaded job per node
####
################################################################

import pylauncher as launcher

##
## Emulate the classic launcher, using a one liner
##

launcher.ClassicLauncher\
    ("commandlines",
     cores="node",
     debug="job+host+exec",
    )
