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
## Execute locally
## -- you need to specify the number of cores you have.
## -- this assumes that process placement is done sensibly.
##

ncores = 24
launcher.LocalLauncher("commandlines",ncores,debug="job") # debug="job+host+task")

