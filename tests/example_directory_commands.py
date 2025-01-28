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

import os
from pylauncher import pylauncher as launcher

##
## A directory based launcher, largely copied from the ClassicLauncher definition
##

jobid = launcher.JobId()
workdir = launcher.NoRandomDir()
debug = "job+command+task+exec"
job = launcher.LauncherJob( delay=2.,
         hostpool=launcher.HostPool( 
            hostlist=launcher.HostListByName(),
            commandexecutor=launcher.SSHExecutor(catch_output=False,workdir=workdir,debug=debug), 
            debug=debug ),
        #hostpool=LocalHostPool(n=5,workdir=workdir,catch_output=False,debug=debug),
        taskgenerator=launcher.TaskGenerator( 
            launcher.DirectoryCommandlineGenerator("dirtest","direxec",debug=debug),
            completion=lambda x:launcher.FileCompletion( taskid=x,
                                    stamproot="expire",stampdir=workdir),
            debug=debug ),
        debug=debug)
job.run()
print job.final_report()

