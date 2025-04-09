#!/usr/bin/env python
################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2025
#### eijkhout@tacc.utexas.edu
####
#### https://github.com/TACC/pylauncher
####
################################################################

import os
import pylauncher

##
## Emulate the classic launcher, using a one liner
##

example="filecore"
print( f"Script: {example}_launcher\n .. running: ClassicLauncher" )
commandlines = "filecorelines"
if not os.path.exists(commandlines):
    raise Exception( f"input does not exist: {commandlines}" )
print( f" .. input: {commandlines}\n" )

pylauncher.ClassicLauncher\
    ( commandlines,cores="file",
     # optional spec of output dir:
     workdir=f"pylauncher_tmp_{example}_{ os.environ['SLURM_JOBID'] }",
     debug="host+exec+job+command")
