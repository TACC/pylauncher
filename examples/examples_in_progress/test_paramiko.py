from pylauncher import *

the_client = ssh_client(HostName())

combase = "touch %s_paramiko_test" % RandomFile()
comcount = 0
def NextCommand():
    global comcount,combase
    comcount += 1
    return combase+str(comcount)

the_client.exec_command( NextCommand() )
print "done1 in home"

line = "cd %s ; %s" % (os.getcwd(),NextCommand())
print "Doing 2 in cwd <<%s>>" % line
the_client.exec_command( line )

line = "( cd %s ; %s ) &" % (os.getcwd(),NextCommand()) 
print "Doing 3 in cwd backgroun: <<%s>>" % line
the_client.exec_command( line )

node = Node(host=HostName())

line = Task( NextCommand(),taskid=comcount ).line_with_completion()
print "Doing 4 officially: <<%s>>" % line
the_client.exec_command( line )

line = Task( NextCommand(),taskid=comcount ).line_with_completion()
line = "cd %s ; %s" % (os.getcwd(),line)
print "Doing 5 in cwd <<%s>>" % line
the_client.exec_command( line )

line = Task( NextCommand(),taskid=comcount ).line_with_completion()
line = "( cd %s ; %s ) &" % (os.getcwd(),line)
print "Doing 6 in cwd <<%s>>" % line
the_client.exec_command( line )
print "\n"

node = Node(host=HostName())
executor = SSHExecutor(workdir=RandomDir(),debug="exec+ssh")
executor.setup_on_node(node)

line = Task( NextCommand(),taskid=comcount ).line_with_completion()
print "Doing 7 officially <<%s>>" % line
executor.execute(line,pool=node)
print "\n"

# and again

#node = Node(host=HostName())
host = HostName()
executor = SSHExecutor(workdir=RandomDir(),debug="exec+ssh")
#executor.setup_on_node(node)
client = ssh_client(host,debug=True)
line = Task( NextCommand(),taskid=comcount ).line_with_completion()
print "Doing 8 explicitly <<%s>>" % line
#executor.execute(line,pool=node)
#fullcommandline = self.cd_env_commandline(command,workdir)
line = executor.wrap(line)
client.exec_command( line ) #("( %s ) &" % fullcommandline)

undefined

task = Task( NextCommand(),taskid=comcount,completion=FileCompletion(taskid=comcount))
line = task.line_with_completion()
line = "( cd %s ; %s ) &" % (os.getcwd(),line)
print "8 is like 6 but FileCompletion in cwd <<%s>>\n\n" % line
the_client.exec_command( line )

executor.cleanup()

node = Node(host=HostName())
executor = SSHExecutor(workdir=RandomDir(),debug="exec+ssh")
executor.setup_on_node(node)

task = Task( NextCommand(),taskid=comcount,
             completion=FileCompletion(taskid=comcount,stampdir=RandomDir()),
             debug="host+task+exec+ssh")
task.start_on_nodes( pool=node )
print "9 uses start_on_nodes\n\n"

executor.cleanup()

task = Task( NextCommand(),taskid=comcount,
             completion=FileCompletion(taskid=comcount,stampdir=RandomDir()),
             debug="host+task+exec+ssh")
task.start_on_nodes( pool=DefaultHostPool( 
                         commandexecutor=SSHExecutor(workdir=RandomDir(),
                                                     debug="exec+ssh"),
                         debug="host+ssh+exec").request_nodes(1) )
print "10 uses ssh to start_on_nodes"

# jobid = JobId()
# job = LauncherJob(
#     hostpool=HostPool( hostlist=NamedHostList(),
#                        commandexecutor=SSHExecutor(debug=debug), debug=debug ),
#     taskgenerator=TaskGenerator( FileCommandlineGenerator(commandfile,cores),
#                                  completion=TmpDirCompletionGenerator
#                                  (stamproot="expire",stampdir="pylauncher_tmp"+str(jobid)),
#                                  debug=debug ),
#     debug=debug,**kwargs)
# job.run()

print "Finished"
