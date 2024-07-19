#!/usr/bin/env python
################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2024
#### eijkhout@tacc.utexas.edu
####
#### This is example is wrong
#### we have core commandlines, without indicating cores=file
#### However, pylauncher can not detect that the corelines 
#### are not valid commands.
####
################################################################

import pylauncher

##
## Emulate the classic launcher, using a one liner
##

pylauncher.ClassicLauncher("corecommandlines",
                           debug="job+command",
                           )

