#!/usr/bin/env python

from pylauncher3 import *

##
## A directory based launcher, largely copied from the ClassicLauncher definition
##

jobid = JobId()
workdir = NoRandomDir()
debug = "job+command+task+exec"
job = LauncherJob( delay=2.,
         hostpool=HostPool( 
            hostlist=HostListByName(),
            commandexecutor=SSHExecutor(catch_output=False,workdir=workdir,debug=debug), 
            debug=debug ),
        #hostpool=LocalHostPool(n=5,workdir=workdir,catch_output=False,debug=debug),
        taskgenerator=TaskGenerator( 
            DirectoryCommandlineGenerator("dirtest","direxec",debug=debug),
            completion=lambda x:FileCompletion( taskid=x,
                                    stamproot="expire",stampdir=workdir),
            debug=debug ),
        debug=debug)
job.run()
print job.final_report()

