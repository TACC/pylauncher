#!/usr/bin/env python
################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2024
#### eijkhout@tacc.utexas.edu
####
#### this tests our correct interpretation of commas in the commandlines
####
################################################################

import pylauncher as launcher

##
## Emulate the classic launcher, using a one liner
##

launcher.ClassicLauncher("commalines",debug="exec")
