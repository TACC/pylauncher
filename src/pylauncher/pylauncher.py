################################################################
####
#### This file is part of the `pylauncher' package
#### for parametric job launching
####
#### Copyright Victor Eijkhout 2010-2024
#### eijkhout@tacc.utexas.edu
####
#### https://github.com/TACC/pylauncher
####
################################################################

pylauncher_version = "4.4"
docstring = \
f"""pylauncher.py version {pylauncher_version}

A python based launcher utility for packaging sequential or
low parallel jobs in one big parallel job

Author: Victor Eijkhout
eijkhout@tacc.utexas.edu
Modifications for PBS-based systems: Christopher Blanton
chris.blanton@gatech.edu
"""
otoelog = """
Change log
4.3
- slurm submit launcher, jobid detection fixed
4.2
- queuestate through explicit option
4.1
- adding stampede3, workdir improvement
4.0 
- turning into a package; all examples updated

3.4
- print flushing
- corespernode parameter
3.3
- adding barrier command
- incorporate frontera-clx
- adding numactl parameter
3.2
- adding LocalLauncher and example,
- adding RemoteLauncher & IbrunRemoteLauncher
3.1
- Modifications for PBS-based systems: Christopher Blanton
  Also: adding longhorn@tacc
3.0
- gradually going over to python3, only print syntax for now
- setting PYLAUNCHER_ENABLED for Lmod

2.7
- more compact task reporting
2.6
- better host detection for s2-skx
2.5
- incorporates Stampede2, minor other edits
2.4
- incorporates Lonestar5
2.3
- supports operation on a MIC
2.2
- introduced ClusterName; HostName is now really the hostname
- unit tests now work outside of a cluster.
2.1
- renamed TACCHostPool -> DefaultHostPool
- proper prefixer for ClassicLauncher
2.0
- complete redesign
1.6
- SLURM support
1.5
- Adding affinity control
1.4
- CD'ing to current directory fixed
1.3
- Tmp directory now internal to job instead of global variable;
can be specified as kwarg to both Job and LauncherJob
- Completion testing now takes only file system access per tick
1.2
- Unique tmp directory
"""

import copy
import glob
import functools
import math
import os
import paramiko
import random
import re
import stat
import shutil
import stat
import subprocess
import sys
import time
import hostlist3 as hs

class LauncherException(Exception):
    """A very basic exception mechanism"""
    def __init__(self,str):
        print(str,flush=True)
        self.str = str
    def __str__(self):
        return self.str
                                
debugtracefile = None
def MakeDebugtracefile(launcherdir):
    global debugtracefile
    debugtracefile = open(launcherdir+"/debugtracefile","w",1)
runtime = float(time.time())
def DebugTraceMsg(msg,sw=False,prefix=""):
    global runtime,debugtracefile
    if not sw: return
    if msg[0]=="\n":
        print
        msg = msg[1:]
    longprefix = ""#"[t=%5.3f] " % time.time()-runtime
    if prefix!="":
        longprefix += prefix+": "
    for l in msg.split("\n"):
        print(longprefix+l,flush=True)
        longprefix = len(longprefix)*" "
    if debugtracefile is not None:
        debugtracefile.write(msg+"\n")
        os.fsync()
def CloseDebugtracefile():
    close(debugtracefile)

randomid = 10
def RandomID():
    global randomid
    randomid += 7
    return randomid
def RandomDir():
    return "./pylauncher_tmpdir%d" % RandomID()
def NoRandomDir():
    dirname = RandomDir()
    if os.path.isdir(dirname):
        shutil.rmtree(dirname)
    return dirname
def MakeRandomDir():
    dirname = RandomDir()
    print("using random dir:",dirname,flush=True)
    try: 
        os.makedirs(dirname,exist_ok=True)
    except OSError:
        if not os.path.isdir(dirname):
            raise
    #if not os.path.isdir(dirname):
    #os.mkdir(dirname)
    return dirname
def RandomFile(base=""):
    fn  = "pylauncher_tmpfile"
    if base!="":
        fn = fn+"-"+base
    return fn+str(RandomID())
def NoRandomFile():
    fn = RandomFile()
    if os.path.isfile(fn):
        os.remove(fn)
    return fn
def RandomNumber(tmax,tmin=0):
    tmin = int(tmin); tmax = int(tmax)
    return int( tmin+(tmax-tmin)*random.random() )

class CountedCommandGenerator():
    """This class is only for the unit tests, it produces a string of `echo 0', `echo 1'
    et cetera commands.

    :param nmax: (keyword, default=-1) maximum number of commands to generate, negative for no maximum
    :param command: (keyword, default==``echo``) the command that will do the counting; sometimes it's a good idea to replace this with ``/bin/true``
    :param catch: (keyword, default None) file where to catch output
    """
    def __init__(self,**kwargs):
        self.__commandcount__ = 0
        self.nmax = kwargs.pop("nmax",-1)
        self.command = kwargs.pop("command","echo")
        self.catch = kwargs.pop("catch",None)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed CountedCommandGenerator args: %s" % str(kwargs))
    def next(self):
        """Return the next unix command string"""
        if self.__commandcount__==self.nmax: raise StopIteration
        thecount = self.__commandcount__; self.__commandcount__ += 1
        command = "%s %d" % (self.command,thecount)
        if self.catch is not None:
            command += " >> %s 2>&1 " % self.catch
        return command
    def __iter__(self): return self

pylauncherBarrierString = "__barrier__"

class SleepCommandGenerator(CountedCommandGenerator):
    """Generator of commandlines `echo 0 ; sleep trand', `echo 1 ; sleep trand'
    where the sleep is a random amount.

    :param tmax: (keyword, default 5) maximum sleep time 
    :param tmin: (keyword, default 1) minimum sleep time
    :param barrier: (keyword, default 0) if >0, insert a barrier statement every that many lines
    """
    def __init__(self,**kwargs):
        self.tmax = kwargs.pop("tmax",5)
        self.tmin = kwargs.pop("tmin",1)
        self.barrier = kwargs.pop("barrier",0)
        self.count = 0; self.last_line_was_barrier = True
        CountedCommandGenerator.__init__(self,catch="/dev/null",**kwargs)
    def next(self):
        if self.barrier>0 and self.count % self.barrier==0 \
                and not self.last_line_was_barrier:
            commandline = pylauncherBarrierString
            self.last_line_was_barrier = True
        else:
            commandline = CountedCommandGenerator.next(self)+\
                " ; sleep %d" % RandomNumber(self.tmax,tmin=self.tmin)
            self.last_line_was_barrier = False
            self.count += 1
        return commandline

def SingleSleepCommand(t,**kwargs):
    """this should not be called in a loop: only for single test"""
    tmin = kwargs.pop("tmin",1)
    return SleepCommandGenerator(nmax=1,tmax=t,tmin=tmin).next()

class Commandline():
    """A Commandline is basically a dict containing at least the following members:

    * command : a unix commandline
    * cores : an integer core count
    * dependencies : dependency stuff.
    """
    def __init__(self,command,**kwargs):
        self.data = {'command':command}
        self.data["cores"] = int( kwargs.pop("cores",1) )
        self.data["dependencies"] = kwargs.pop("dependencies",None)
    def __getitem__(self,ind):
        return self.data[ind]
    def __str__(self):
        r = "command=<<%s>>, cores=%d" % (self["command"],self["cores"])
        return r

class CommandlineGenerator():
    """An iteratable class that generates a stream of ``Commandline`` objects.

    The behaviour of the generator depends on the ``nmax`` parameter:

    * nmax is None: exhaust the original list
    * nmax > 0: keep popping until the count is reached; if the initial list is shorter, someone will have to fill it, which this class is not capable of
    * nmax == 0 : iterate indefinitely, wait for someone to call the ``finish`` method

    In the second and third scenario it can be the case that the list is empty.
    In that case, the generator will yield a COMMAND that is ``stall``.

    :param list: (keyword, default [] ) initial list of Commandline objects
    :param nax: (keyword, default None) see above for explanation
    """
    def __init__(self,**kwargs):
        self.list = [ e for e in kwargs.pop("list",[]) ]
        self.ncommands = len(self.list); self.njobs = 0; self.stopped = False
        nmax = kwargs.pop("nmax",None)
        if nmax is None:
            if len(self.list)==0:
                raise LauncherException("Empty list requires nmax==0")
            self.nmax = len(self.list)
        else: self.nmax = nmax
        debugs = kwargs.pop("debug","")
        self.debug = re.search("command",debugs)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed CommandlineGenerator args: %s" \
                                        % str(kwargs))
    def finish(self):
        """Tell the generator to stop after the commands list is depleted"""
        DebugTraceMsg("declaring the commandline generator to be finished",
                      self.debug,prefix="Cmd")
        self.nmax = self.njobs+len(self.list)
    def abort(self):
        """Stop the generator, even if there are still elements in the commands list.
        Where is this called?"""
        DebugTraceMsg("gettingthe commandline generator to abort",
                      self.debug,prefix="Cmd")
        self.stopped = True
    def next(self):
        """Produce the next Commandline object, or return an object telling that the
        generator is stalling or has stopped"""
        if self.stopped:
            DebugTraceMsg("stopping the commandline generator",
                          self.debug,prefix="Cmd")
            return Commandline("stop")
            #raise StopIteration
        elif ( len(self.list)==0 and self.nmax!=0 ) or \
                ( self.nmax>0 and self.njobs==self.nmax ):
            DebugTraceMsg("time to stop commandline generator",
                          self.debug,prefix="Cmd")
            return Commandline("stop")
            #raise StopIteration
        elif len(self.list)>0:
            j = self.list[0]; self.list = self.list[1:]
            DebugTraceMsg("Popping command off list <<%s>>" % str(j),
                          self.debug,prefix="Cmd")
            self.njobs += 1; return j
        else:
            return Commandline("stall")
    def __iter__(self): return self
    def __len__(self): return len(self.list)

class ListCommandlineGenerator(CommandlineGenerator):
    """A generator from an explicit list of commandlines.

    * cores is 1 by default, other constants allowed.
    """
    def __init__(self,**kwargs):
        cores = kwargs.pop("cores",1)
        commandlist = [ Commandline(l,cores=cores) for l in kwargs.pop("list",[]) ]
        CommandlineGenerator.__init__(self,list=commandlist,**kwargs)

class FileCommandlineGenerator(CommandlineGenerator):
    """A generator for commandline files:
    blank lines and lines starting with the comment character '#' are ignored

    * cores is 1 by default, other constants allowed.
    * cores=='file' means the file has << count,command >> lines
    * if the file has core counts, but you don't specify the 'file' value, they are ignored.

    :param filename: (required) name of the file with commandlines
    :param cores: (keyword, default 1) core count to be used for all commands
    :param dependencies: (keyword, default False) are there task dependencies?
    """
    def __init__(self,filename,**kwargs):
        cores = kwargs.pop("cores",1)
        dependencies = kwargs.pop("dependencies",False)
        file = open(filename); commandlist = []
        count = 0
        for line in file.readlines():
            ## Parse the line from file.
            line = line.strip()
            if re.match('^ *#',line) or re.match('^ *$',line):
                continue # skip blank and comment
            ## Default dependencies
            ## I don't even know what this means.
            td = str(count)
            ## Parse dependency
            if dependencies:
                split = line.split(",",2)
                if len(split)<3:
                    raise LauncherException("No task#/dependency found <<%s>>" % split)
                c,td,l = split
            elif re.match("barrier",line):
                l = pylauncherBarrierString; c = 1
            elif cores=="file":
                ## each line has a core count
                if re.match("[0-9]+,",line):
                    split = line.split(",",1)
                    c,l = split
                else:
                    raise LauncherException \
                        (f"Can not parse line as having a core prefix: <<{line}>>")
            else:
                ## default case: 
                ## cores come from somewhere else
                c = cores
                ## line is line
                l = line
            commandlist.append( Commandline(l,cores=c,dependencies=td) )
            count += 1
        CommandlineGenerator.__init__(self,list=commandlist,**kwargs)

class StateFileCommandlineGenerator(CommandlineGenerator):
    """A generator for the lines in a queuestate restart file.
    Otherwise this has all the code of the FileCommandlineGenerator.
    Ugly.
    """
    def __init__(self,filename,**kwargs):
        cores = kwargs.pop("cores",1)
        dependencies = kwargs.pop("dependencies",False)
        file = open(filename); commandlist = []
        count = 0; skipping = False
        for line in file.readlines():
            line = line.strip()
            if re.match('^ *#',line) or re.match('^ *$',line):
                continue # skip blank and comment
            # skip completed lines, include running and queued
            if re.match("running",line):
                skipping = False; continue
            elif re.match("queued",line):
                skipping = False; continue
            elif re.match("completed",line):
                skipping = True; continue
            if skipping:
                continue
            # make commandline from all lines that are not skipped
            line = line.split(":",1)[1]
            split = line.split(",",1)
            if len(split)==1:
                c = cores; l = split[0]
            else:
                c,l = split
                td = str(count)
            if cores=="file":
                if not re.match("[0-9]+",c):
                    raise LauncherException \
                        ("First field <<%s>> is not a core count; line:\n<<%s>>" % (c,line) )
            else:
                c = cores
            commandlist.append( Commandline(l,cores=c) )
            count += 1
        CommandlineGenerator.__init__(self,list=commandlist,**kwargs)

class DynamicCommandlineGenerator(CommandlineGenerator):
    """A CommandlineGenerator with an extra method:

    ``append``: add a Commandline object to the list

    The 'nmax=0' parameter value makes the generator keep expecting new stuff.
    """
    def __init__(self,**kwargs):
        nmax = kwargs.pop("nmax",None)
        if nmax is not None:
            raise LauncherException("Dynamic launcher can not have nmax specification")
        CommandlineGenerator.__init__(self,nmax=0,**kwargs)
        self.n_append = 0
    def append(self,command):
        """Append a unix command to the internal structure of the generator"""
        if not isinstance(command,(Commandline)):
            raise LauncherException("append argument needs to be Commandline object")
        DebugTraceMsg("appending to command list <<%s>>" % str(command),
                      self.debug,prefix="Cmd")
        command_no = self.ncommands
        self.list.append(command); self.ncommands += 1
        return command_no

class DirectoryCommandlineGenerator(DynamicCommandlineGenerator):
    """A CommandlineGenerator object based on finding files in a directory.

    :param command_directory: (directory name, required) directory where commandlines are found; unlike launcher job work directories, this can be reused.
    :param commandfile_root: (string, required) only files that start with this, followed by a dash, are inspected for commands. A file can contain more than one command.
    :param cores: (keyword, optional, default 1) core count for the commandlines.
    """
    def __init__(self,command_directory,commandfile_root,**kwargs):
        self.command_directory = command_directory
        self.commandfile_root = commandfile_root
        self.finish_name = commandfile_root+"-finished"
        self.cores = kwargs.pop("cores",1)
        self.scheduled_jobs = []
        DynamicCommandlineGenerator.__init__(self,**kwargs)
    def next(self):
        """ List the directory and iterate over the commandfiles:

        * ignore any open files, which are presumably still being written
        * if they are marked as scheduled, ignore
        * if there is a file ``finish-nnn``, mark job nnn as finished
        * if they are not yet scheduled, call ``append`` with a ``Commandline`` object

        If the finish name is present, and all scheduled jobs are finished, finish the generator.
        """
        dircontents = os.listdir(self.command_directory)
        print("contents",dircontents,flush=True)
        #
        for f in dircontents:
            if re.match(self.commandfile_root,f):
                long_filename = os.path.join(self.command_directory,f)
                try: # if the file is still being written, we ignore it
                    testopen = open(long_filename,"a+")
                    testopen.close()
                except IOError:
                    print("file still open",f,flush=True)
                    continue
                jobnumber = f.split('-')[1]
                if jobnumber not in self.scheduled_jobs:
                    self.scheduled_jobs.append(jobnumber)
                    print("scheduling job",jobnumber,flush=True)
                    with open(long_filename,"r") as commandfile:
                        for l in commandfile:
                            l = l.strip()
                            self.append( Commandline( l,cores=self.cores ) )
        #
        if self.finish_name in dircontents:
            allfinished = True
            if allfinished:
                self.finish()
        return CommandlineGenerator.next(self)

def MakeRandomCommandFile(fn,ncommand,**kwargs):
    """Make file with commandlines and occasional comments and blanks.

    :param cores: (keyword, default=1) corecount, if this is 1 we put nothing in the file, larger values and \"file\" (for random) go into the file
    """
    cores = kwargs.pop("cores",1)
    debug = kwargs.pop("debug",0)
    if debug==0:
        generator = kwargs.pop("generator",CountedCommandGenerator(nmax=ncommand,catch="/dev/null"))
    else:
        generator = kwargs.pop("generator",CountedCommandGenerator(nmax=ncommand))
    if len(kwargs)>0:
        raise LauncherException("Unprocessed args: %s" % str(kwargs))
    commandlines = open(fn,"w")
    for i in range(ncommand):
        if i%5==0:
            commandlines.write("# arbitrary comment\n")
        if i%7==0:
            commandlines.write("\n")
        c = generator.next()
        if cores>1:
            c = "%d,%s" % (cores,c)
        commandlines.write( c+"\n" )
    commandlines.close()

def MakeRandomSleepFile(fn,ncommand,**kwargs):
    """make file with sleep commandlines and occasional comments and blanks"""
    tmax = kwargs.pop("tmax",6)
    tmin = kwargs.pop("tmin",1)
    MakeRandomCommandFile\
        (fn,ncommand,generator=SleepCommandGenerator(nmax=ncommand,tmax=tmax,tmin=tmin),
         **kwargs)

class Completion():
    """Define a completion object for a task. 

    The base class doesn't do a lot: it immediately returns true on the 
    completion test.
    
    The kwargs arguments will probably be caught by derived classes.
    """
    def __init__(self,**kwargs):
        self.taskid = kwargs.pop("taskid",0)
        self.workdir = kwargs.pop("workdir",".")
        debugs = kwargs.pop("debug","")
        self.debug = re.search("task",debugs)
    def attach(self,txt):
        """Attach a completion to a command, giving a new command.
        Default is to return the line unaltered."""
        return txt
    def test(self):
        """Test whether the task has completed"""
        DebugTraceMsg("default completion test is true",
                      self.debug,prefix="Task")
        return True

class WrapCompletion(Completion):
    """WrapCompletion is the most common type of completion. It appends
    to a command the creation of a zero size file with a unique name.
    The completion test then tests for the existence of that file.

    :param taskid: (keyword, required) this has to be unique. Unfortunately we can not test for that.
    """
    def __init__(self,**kwargs):
        Completion.__init__(self,**kwargs)
    def stampname(self):
        """Internal function that gives the name of the stamp file,
        including directory path"""
        return "%s/%s%s" % (self.workdir,"expire",str(self.taskid))
    def attach(self,txt):
        """Append a 'touch' command to the txt argument"""
        os.system("mkdir -p %s" % self.workdir)
        if re.match('^[ \t]*$',txt):
            command_with_stamp = f"touch {self.stampname()}"
        else:
            command_with_stamp = f"( {txt} ) ; touch {self.stampname()}"
        return command_with_stamp
    def test(self):
        """Test for the existence of the stamp file"""
        stampfile = self.stampname()
        stamptest = os.path.isfile(stampfile)
        if stamptest:
            print(f"stamp file <<{stampfile}>> detected")
            DebugTraceMsg(f"stamp file <<{stampfile}>> detected",
                          self.debug,prefix="Task")
        return stamptest
    def cleanup(self):
        os.system("rm -f %s" % self.stampname())

class BareCompletion(Completion):
    """BareCompletion does not wrap, so it uses the default attach method,
    but tests on the stamp file anyway.
    Presumably it gets created another way.

    :param taskid: (keyword, required) this has to be unique. Unfortunately we can not test for that.
    """
    def __init__(self,**kwargs):
        Completion.__init__(self,**kwargs)
    def stampname(self):
        """Internal function that gives the name of the stamp file,
        including directory path"""
        return "%s/%s%s" % (self.workdir,"expire",str(self.taskid))
    def test(self):
        """Test for the existence of the stamp file"""
        stampfile = self.stampname()
        stamptest = os.path.isfile(stampfile)
        if stamptest:
            print(f"stamp file <<{stampfile}>> detected")
            DebugTraceMsg(f"stamp file <<{stampfile}>> detected",
                          self.debug,prefix="Task")
        return stamptest
    def cleanup(self):
        os.system("rm -f %s" % self.stampname())

class Task():
    """A Task is an abstract object associated with a commandline

    :param command: (required) Commandline object; note that this contains the core count
    :param completionclass: (keyword, required) Completion class name
    :param taskid: (keyword) identifying number of this task; has to be unique in a job, also has to be equal to the taskid of the completion
    :param linewrapper: (keyword, required)
    :param debug: (keyword, optional) string of debug keywords
    """
    def __init__(self,command,**kwargs):
        self.command = command["command"]

        debugs = kwargs.get("debug","")
        self.debug = re.search("task",debugs)
        self.workdir = kwargs.pop("workdir",None)

        # instantiate a completion for this id.
        self.taskid = kwargs.pop("taskid")
        self.completion = kwargs.pop("completionclass")\
                          (taskid=self.taskid,workdir=self.workdir)

        self.size = command["cores"]
        self.has_started = False
        DebugTraceMsg("created task <<%s>>" % str(self),self.debug,prefix="Task")
        self.nodes = None
    def start_on_nodes(self,**kwargs):
        """Start the task.

        :param pool: HostLocator object (keyword, required) : this describes the nodes on which to start the task
        :param commandexecutor: (keyword, optional) prefixer routine, by default the commandexecutor of the pool is used

        This sets ``self.startime`` to right before the execution begins. We do not keep track
        of the endtime, but instead set ``self.runningtime`` in the ``hasCompleted`` routine.
        """
        self.starttick = kwargs.pop("starttick",0)
        self.pool = kwargs.pop("pool",None)
        if self.pool is None:
            self.pool = LocalHostPool(nhosts=self.size,debug=self.debugs
                                      ).request_nodes(self.size)
        elif isinstance(self.pool,(Node)):
            if self.size>1:
                raise LauncherException("Can not start size=%d on sing Node" % self.size)
            self.pool = OneNodePool( self.pool,debug=self.debugs ).request_nodes(self.size)
        if not isinstance(self.pool,(HostLocator)):
            raise LauncherException("Invalid locator object")
        if len(kwargs)>0:
            raise LauncherException("Unprocessed Task.start_on_nodes args: %s" % str(kwargs))
        # wrap with stamp detector
        wrapped = self.line_with_completion()
        # line = re.sub("PYL_ID",str(self.taskid),self.command)
        # self.actual_command = line
        # wrapped = self.completion.attach(line)

        # and here we go
        self.execute_on_pool(wrapped)
    def execute_on_pool(self,line):
        DebugTraceMsg(
            "starting task id=%d of size %d on <<%s>>\nin cwd=<<%s>>\ncmd=<<%s>>" % \
                (self.taskid,self.size,str(self.pool),
                 os.getcwd(),line),
            self.debug,prefix="Task")
        self.starttime = time.time()
        commandexecutor = self.pool.pool.commandexecutor
        commandexecutor.execute(line,pool=self.pool,id=self.taskid)
        self.has_started = True
        DebugTraceMsg("started %d" % self.taskid,self.debug,prefix="Task")
    def isRunning(self):
        return self.has_started
    def line_with_completion(self):
        """Return the task's commandline with completion attached"""
        line = re.sub("PYL_ID",str(self.taskid),self.command)
        self.actual_command = line
        return self.completion.attach(line)
    def hasCompleted(self):
        """Execute the completion test of this Task"""
        completed = self.has_started and self.completion.test()
        if completed:
            ## print(f"completion: {self.completion}")
            self.runningtime = time.time()-self.starttime
            DebugTraceMsg("completed %d in %5.3f" % (self.taskid,self.runningtime),
                          self.debug,prefix="Task")
        return completed
    def __repr__(self):
        s = f"Task id={self.taskid}, cmd=<<{self.command}>>, pool size={self.size}"
        return s

class WrappedTask(Task):
    def __init__(self,command,**kwargs):
        id = kwargs.get("taskid")
        debugs = kwargs.get("debug","")
        debug = re.search("task",debugs)
        DebugTraceMsg(f"creating wrapped task id={id}",debug,prefix="Task")
        # the kwargs include taskid
        Task.__init__(self,command,completionclass=WrapCompletion,**kwargs)
class BareTask(Task):
    def __init__(self,command,**kwargs):
        id = kwargs.get("taskid")
        debugs = kwargs.get("debug","")
        debug = re.search("task",debugs)
        DebugTraceMsg(f"creating bare task id={id}",debug,prefix="Task")
        # the kwargs include taskid
        Task.__init__(self,command,completionclass=BareCompletion,**kwargs)

class RandomSleepTask(Task):
    """Make a task that sleeps for a random amount of time.
    This is for use in many many unit tests.

    :param taskid: unique identifier (keyword, required)
    :param t: maximum running time (keyword, optional; default=10)
    :param tmin: minimum running time (keyword, optional; default=1)
    :param completion: Completion object (keyword, optional; if you leave this unspecified, the next two parameters become relevant
    """
    def __init__(self,**kwargs):
        taskid = kwargs.pop("taskid",-1)
        if taskid==-1:
            raise LauncherException("Need an explicit sleep task ID")
        t = kwargs.pop("t",10); tmin = kwargs.pop("tmin",1);
        completion = kwargs.pop("completion",None)
        if completion is None:
            completion = FileCompletion(taskid=taskid,workdir=workdir)
        command = SleepCommandGenerator(nmax=1,tmax=t,tmin=tmin).next()
        Task.__init__(self,Commandline(command),taskid=taskid,completion=completion,**kwargs)
        
#
# different ways of starting up a job
def launcherqsubber(task,line,hosts,poolsize):
    command = "qsub %s" % line
    return command

class Node():
    """A abstract object for a slot to execute a job. Most of the time
    this will correspond to a core.

    A node can have a task associated with it or be free."""
    def __init__(self,host=None,core=None,nodeid=-1,phys_core="0-0"):
        self.hostname = host; self.core = core; self.phys_core = phys_core
        self.nodeid = nodeid; 
        # two initializations before the first ``release`` call:
        self.free = None; self.tasks_on_this_node = -1
        self.release()
    def occupyWithTask(self,taskid):
        """Occupy a node with a taskid"""
        self.free = False; self.taskid = taskid
    def release(self):
        """Make a node unoccupied"""
        if self.free is not None and self.free:
            raise LauncherException("Attempting to release a free node")
        self.free = True; self.taskid = -1
        self.tasks_on_this_node += 1
    def isfree(self):
        """Test whether a node is occupied"""
        return self.free
    def nodestring(self):
        if self.free: return "X"
        else:         return str( self.taskid )
    def __str__(self):
        return "h:%s, c:%s, id:%s, p:%s" % \
            (self.hostname,str(self.core),str(self.nodeid),str(self.phys_core))

class HostLocator():
    """A description of a subset from a HostPool. A locator
    object is typically created when a task asks for a set of nodes
    from a HostPool. Thus, a locator inherits the executor
    from the host pool from which it is taken.

    The only locator objects allowed at the moment are consecutive subsets.

    :param pool: HostPool (optional)
    :param extent: number of nodes requested
    :param offset: location of the first node in the pool

    """
    def __init__(self,pool=None,extent=None,offset=None):
        if extent is None or offset is None:
            raise LauncherException("Please specify extent and offset")
        self.pool=pool; self.offset=offset; self.extent=extent
    def __getitem__(self,key):
        index = self.offset+key
        if key>=self.extent:
            raise LauncherException("Index %d out of range for pool" % index)
        node = self.pool[index]
        if not isinstance(node,(Node)):
            raise LauncherException("Strange node type: <<%s>> @ %d" % (str(node),key) )
        return node
    def firsthost(self):
        node = self[0]#.pool[self.offset]
        return node.hostname
    def first_range(self):
        node = self[0]
        return node.phys_core
    def __len__(self):
        return self.extent
    def __str__(self):
        return "Locator: size=%d offset=%d <<%s>>" % \
            (self.extent,self.offset,str([ str(self[i]) for i in range(self.extent) ]))

def HostName():
    """This just returns the hostname. See also ``ClusterName``."""
    import socket
    return socket.gethostname()

class HostPoolBase():
    """A base class that defines some methods and sets up
    the basic data structures.

    :param commandexecutor: (keyword, optional, default=``LocalExecutor``) the ``Executor`` object for this host pool
    :param workdir: (keyword, optional) the workdir for the command executor
    :param debug: (keyword, optional) a string of debug types; if this contains 'host', anything derived from ``HostPoolBase`` will do a debug trace
    """
    def __init__(self,**kwargs):
        self.nodes = []
        self.commandexecutor = kwargs.pop("commandexecutor",None)
        workdir = kwargs.pop("workdir",None)
        if self.commandexecutor is None:
            self.commandexecutor = LocalExecutor(workdir=workdir)
        elif workdir is not None:
            raise LauncherException("workdir arg is ignored with explicit executor")
        self.debugs = kwargs.pop("debug","")
        self.debug = re.search("host",self.debugs)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed HostPool args: %s" % str(kwargs))
    def append_node(self,host="localhost",core=0,phys_core="0-0"):
        """Create a new item in this pool by specifying either a Node object
        or a hostname plus core number. This function is called in a loop when a
        ``HostPool`` is created from a ``HostList`` object."""
        if isinstance(host,(Node)):
            node = host
        else:
            node = Node(host,core,nodeid=len(self.nodes),phys_core=phys_core)
        self.nodes.append( node )
        self.commandexecutor.setup_on_node(node)
    def __len__(self):
        return len(self.nodes)
    def __getitem__(self,i):
        return self.nodes[i]
    def hosts(self,pool):
        return [ self[i] for i in pool ]
    def unique_hostnames(self,pool=None):
        """Return a list of unique hostnames. In general each hostname appears
        16 times or so in a HostPool since each core is listed."""
        if pool is None:
            pool = range(len(self))
        u = []
        for h in self.hosts(pool):
            name = h.hostname
            if not name in u:
                u.append(name)
        return sorted(u)
    def request_nodes(self,request):
        """Request a number of nodes; this returns a HostLocator object"""
        DebugTraceMsg("request %d nodes" % request,self.debug,prefix="Host")
        start = 0; found = False    
        while not found:
            if start+request>len(self.nodes):
                return None
            for i in range(start,start+request):
                found = self[i].isfree()
                if not found:
                    start = i+1; break
        if found:
            locator = HostLocator(pool=self,offset=start,extent=request)
            DebugTraceMsg("returning <<%s>>" % str(locator),self.debug,prefix="Host")
            return locator
        else: 
            DebugTraceMsg("could not locate",self.debug,prefix="Host")
            return None
    def occupyNodes(self,locator,taskid):
        """Occupy nodes with a taskid

        Argument:
        * locator : HostLocator object
        * taskid : like the man says
        """
        nodenums = range(locator.offset,locator.offset+locator.extent)
        DebugTraceMsg("occupying nodes %s with %d" % (str(nodenums),taskid),
                      self.debug,prefix="Host")
        for n in nodenums:
            self[n].occupyWithTask(taskid)
    def releaseNodesByTask(self,taskid):
        """Given a task id, release the nodes that are associated with it"""
        done = False
        for n in self.nodes:
            if n.taskid==taskid:
                DebugTraceMsg("releasing %s, core %s"
                              % (str(n.hostname),str(n.core)),
                              self.debug,prefix="Host")
                n.release(); done = True
        if not done:
            raise LauncherException("Could not find nodes associated with id %s"
                                    % str(taskid))
    def release(self):
        """If the executor opens ssh connections, we want to close them cleanly."""
        self.commandexecutor.terminate()
    def final_report(self):
        """Return a string that reports how many tasks were run on each node."""
        counts = [ n.tasks_on_this_node for n in self ]
        message = """
Host pool of size %d.

Number of tasks executed per node:
max: %d
avg: %d
""" % ( len(self),max(counts),sum(counts)/len(counts) )
        return message
    def printhosts(self):
        hostlist = ""
        for i,n in enumerate(self.nodes):
            hostlist += "%d : %s\n" % (i,str(n))
        return hostlist.strip()
    def __repr__(self):
        hostlist = str ( [ "%d:%s" % ( i,n.nodestring() ) for i,n in enumerate(self.nodes) ] )
        return hostlist

class OneNodePool(HostPoolBase):
    """This class is mostly for testing: it allows for a node to function
    as a host pool so that one can start a task on it."""
    def __init__(self,node,**kwargs):
        HostPoolBase.__init__(self,**kwargs)
        if not isinstance(node,(Node)):
            raise LauncherException("Invalid node type <<%s>>" % node)
        self.append_node(node)

class HostPool(HostPoolBase):
    """A structure to manage a bunch of Node objects.
    The main internal object is the ``nodes`` member, which 
    is a list of Node objects.

    :param nhosts: the number of slots in the pool; this will use the localhost
    :param hostlist: HostList object; this takes preference over the previous option
    :param commandexecutor: (optional) a prefixer routine, by default LocalExecutor
    """
    def __init__(self,**kwargs):
        workdir = kwargs.pop("workdir",None)
        HostPoolBase.__init__\
            (self,
             commandexecutor=kwargs.pop\
                 ("commandexecutor",LocalExecutor(workdir=workdir)),
             debug=kwargs.pop("debug",""))
        hostlist = kwargs.pop("hostlist",None)
        if hostlist is not None and not isinstance(hostlist,(HostList)):
            raise LauncherException("hostlist argument needs to be derived from HostList")
        nhosts = kwargs.pop("nhosts",None)
        if hostlist is not None:
            if self.debug:
                print("Making hostpool on %s" % str(hostlist),flush=True)
            nhosts = len(hostlist)
            for h in hostlist:
                self.append_node(host=h['host'],core = h['core'],phys_core=h['phys_core'])
        elif nhosts is not None:
            if self.debug:
                print("Making hostpool size %d on localhost" % nhosts,flush=True)
            localhost = HostName()
            hostlist = [ localhost for i in range(nhosts) ]
            for i in range(nhosts):
                self.append_node(host=localhost)
        else: raise LauncherException("HostPool creation needs n or list")
        #self.nhosts = nhosts
        if len(kwargs)>0:
            raise LauncherException("Unprocessed HostPool args: %s" % str(kwargs))
        DebugTraceMsg("Created host pool from <<%s>>" % str(hostlist),self.debug,prefix="Host")
    def __del__(self):
        """The ``SSHExecutor`` class creates a permanent ssh connection, 
        which we try to release by this mechanism."""
        DebugTraceMsg("Releasing nodes",self.debug,prefix="Host")
        for node in self:
            self.commandexecutor.release_from_node(node)

class HostList():
    """Object describing a list of hosts. Each host is a dictionary
    with a ``host`` and ``core``  and ``phys_core`` field.

    Arguments:

    * list : list of hostname strings
    * tag : something like ``.tacc.utexas.edu`` may be necessary to ssh to hosts in the list

    This is an iteratable object; it yields the host/core dictionary objects.
    """
    def __init__(self,hostlist=[],tag="",**kwargs):
        self.debug = re.search("host", kwargs.get("debug","") )
        self.hostlist = []; self.tag = tag; self.uniquehosts = []
        for h in hostlist:
            self.append(h)
    def append(self,h,c=0,p="0-0"):
        """
        Arguments:

        * h : hostname
        * c (optional, default zero) : core number
        * p (optional, default zero) : physical core range
        """
        if not re.search(self.tag,h):
            h = h+self.tag
        if h not in self.uniquehosts:
            self.uniquehosts.append(h)
        #if self.debug:
        DebugTraceMsg("Adding location <<{}>>:{} (phys core {})".format(h,c,p),
                      self.debug,prefix="Host")
        self.hostlist.append( { 'host':h, 'core':c, 'phys_core':p } )
    def __len__(self):
        return len(self.hostlist)
    def __iter__(self):
        for h in self.hostlist:
            yield h
    def __str__(self):
        return str(self.hostlist)

####
#### Customizable section
####
class SGEHostList(HostList):
    def __init__(self,**kwargs):
        HostList.__init__(self,**kwargs)
        hostfile = os.environ["PE_HOSTFILE"]
        with open(hostfile,"r") as hostfile:
            for h in hostfile:
                line = h.strip(); line = line.split(); host = line[0]; n = line[1]
                for i in range(int(n)):
                    self.append(host,i)

class SLURMHostList(HostList):
    def __init__(self,**kwargs):
        HostList.__init__(self,**kwargs)
        hlist_str = os.environ["SLURM_NODELIST"]
        p = int(os.environ["SLURM_NNODES"])
        N = int(os.environ["SLURM_NPROCS"])
        jobs_per_node = int(N/p) # requested cores per node
        try :
            # SLURM_JOB_CPUS_PER_NODE=56(x2)
            cores_per_node = os.environ["SLURM_TASKS_PER_NODE"]
            cores_per_node = re.search(r'([0-9]+)',cores_per_node).groups()[0]
            cores_per_node = int(cores_per_node)
            cores_per_node = kwargs.get("ncores",cores_per_node) # not elegant
            print("Detecting %d cores per node" % cores_per_node,flush=True)
        except:
            print("Could not detect physical cores per node, setting to 1",flush=True)
            cores_per_node = 1
        cpn_override = kwargs.get("corespernode",None)
        if cpn_override:
            cores_per_node = int( cpn_override )
            print( "Override of SLURM value: using %d cores per node" % cores_per_node ,flush=True)
        cores_per_job = int( cores_per_node / jobs_per_node )
        hlist = hs.expand_hostlist(hlist_str)
        for h in hlist:
            for i in range(jobs_per_node):
                job_core = "%d-%d" % ( i * cores_per_job, (i+1) * cores_per_job-1 )
                self.append(h,i,job_core)
# SLURM_TASKS_PER_NODE=48
# SLURM_NPROCS=48
# SLURM_TACC_CORES=48
# SLURM_CPUS_ON_NODE=96
# SLURM_JOB_CPUS_PER_NODE=96

class PBSHostList(HostList):
    def __init__(self,**kwargs):
        HostList.__init__(self,**kwargs)
        hostfile = os.environ["PBS_NODEFILE"]
        with open(hostfile,'r') as hostfile:
            myhostlist = hostfile.readlines()
            #for host in myhostlist:
            #    self.append(host.rstrip(),1)
            for i in range(len(myhostlist)):
                myhostlist[i] = myhostlist[i].rstrip()
                self.append(myhostlist[i],1)

class ListHostList(HostList):
    """A HostList class constructed from an explicit list of hosts.
    Great for notebook applications where the resources are
    externally acquired.

    Keyword parameter:

    :param ppn : processes per node, typically number of cores on a node

    """
    def __init__(self,hostlist,**kwargs):
        HostList.__init__(self)
        ppn = kwargs.get("ppn",1)
        for h in hostlist:
            for p in range(ppn):
                self.append(h)

def ClusterName():
    """Assuming that a node name is along the lines of ``c123-456.cluster.tacc.utexas.edu``
    this returns the second member. Otherwise it returns None.
    """
    # name detection based on environment variables
    if "TACC_SYSTEM" in os.environ:
        system = os.environ["TACC_SYSTEM"]
        if "TACC_NODE_TYPE" in os.environ:
            system += "-" + os.environ["TACC_NODE_TYPE"]
        return system

    # name detection by splitting TACC hostname
    longname = HostName(); namesplit = longname.split(".")
    # case: mic on stampede
    nodesplit = namesplit[0].split("-")
    if len(nodesplit)==3 and nodesplit[2] in ["mic0","mic1"]:
        return "mic"
    # case: tacc cluster node
    if re.match("nid[0-9]",namesplit[0]):
        return "ls5"
    elif "tacc" in namesplit:
        if len(namesplit)>1 and re.match("c[0-9]",namesplit[0]):
            return namesplit[1]
        else: return None
    # Non-TACC example, this is for Georgia Instiute of Technology's PACE
    if "pace" in namesplit:
        return namesplit[1]
    # case: unknown
    return None

def ClusterHasSharedFileSystem():
    """This test is only used in some unit tests.
    The matching tests accomodate clusters with TACC_NODE_TYPE values.
    """
    clustername = ClusterName()
    return clustername in ["mic","ls4","ls5","ls6","maverick",] \
        or re.match('stampede2',clustername) or re.match('stampede3',clustername)

def JobId():
    """This function is installation dependent: it inspects the environment variable
    that holds the job ID, based on the actual name of the host (see
     ``HostName``): this should only return a number if we are actually in a job.
    """
    hostname = ClusterName()
    if "SLURM_JOB_ID" in os.environ.keys():
        # case SLURM
        return os.environ["SLURM_JOB_ID"]
    elif "PBS_JOBID" in os.environ.keys():
        # case PBS
        return os.environ["PBS_JOBID"]
    elif hostname in ["pace"]:
        return os.environ["PBS_JOBID"]
    else:
        return None

def HostListByName(**kwargs):
    """Give a proper hostlist. Currently this work for the following hosts:

    * ``ls5``: Lonestar5 at TACC, using SLURM
    * ``ls6``: Lonestar6 at TACC, using SLURM
    * ``maverick``: Maverick at TACC, using SLURM
    * ``stampede``: Stampede at TACC, using SLURM
    * ``frontera`` : Frontera at TACC, using SLURM
    * ``longhorn`` : Longhorn at TACC, using SLURM
    * ``frontera*'' : Frontera at TACC, using SLRUM
    * ``pace`` : PACE at Georgia Tech, using PBS
    * ``mic``: Intel Xeon PHI co-processor attached to a compute node

    We return a trivial hostlist otherwise.
    """
    debugs = kwargs.pop("debug","")
    debug = re.search("host",debugs)
    cluster = ClusterName()
    if cluster=="ls4":
        hostlist = SGEHostList(tag=".ls4.tacc.utexas.edu",**kwargs)
    elif cluster=="ls5": # ls5 nodes don't have fully qualified hostname
        hostlist = SLURMHostList(tag="",**kwargs)
    elif cluster=="ls6":
        hostlist = SLURMHostList(tag=".ls6.tacc.utexas.edu",**kwargs)
    elif cluster=="maverick":
        hostlist = SLURMHostList(tag=".maverick.tacc.utexas.edu",**kwargs)
    elif re.match('stampede2',cluster):
        hostlist = SLURMHostList(tag=".stampede2.tacc.utexas.edu",**kwargs)
    elif re.match('stampede3',cluster):
        hostlist = SLURMHostList(tag=".stampede3.tacc.utexas.edu",**kwargs)
    elif re.match("frontera",cluster):
        hostlist = SLURMHostList(
            tag=".frontera.tacc.utexas.edu",**kwargs)
    elif cluster=="longhorn":
        hostlist = SLURMHostList(tag=".longhorn.tacc.utexas.edu",**kwargs)
    elif cluster=="mic":
        hostlist = HostList( ["localhost" for i in range(60)] )
    elif cluster in ['pace']:
        return PBSHostList(**kwargs)
    else:
        hostlist = HostList(hostlist=[HostName()])
    if debug:
        print("Hostlist on %s  of size %d: %s" % (cluster,len(hostlist),str(hostlist)),flush=True)
    return hostlist
        
class DefaultHostPool(HostPool):
    """A HostPool object based on the hosts obtained from the
    ``HostListByName`` function, and using the ``SSHExecutor`` function.
    """
    def __init__(self,**kwargs):
        debugs = kwargs.pop("debug","")
        hostlist = kwargs.pop("hostlist",HostListByName(debug=debugs))
        commandexecutor = kwargs.pop("commandexecutor",None)
        if commandexecutor is None:
            if ClusterName() is not None:
                commandexecutor = SSHExecutor(
                    debug=debugs,force_workdir=kwargs.pop("force_workdir",False))
            else:
                commandexecutor = LocalExecutor(
                    debug=debugs,force_workdir=kwargs.pop("force_workdir",False))
        HostPool.__init__( self, hostlist=hostlist,
                           commandexecutor=commandexecutor,
                           debug=debugs, **kwargs )

class LocalHostPool(HostPool):
    """A host pool based on just the localhost, using the ``LocalExecutor``. This is for testing purposes.

    :param nhosts: (keyword, optional, default=1) number of times the localhost should be listed
    :param workdir: (keyword, optional) workdir for the commandexecutor
    """
    def __init__(self,**kwargs):
        nhosts = kwargs.pop("nhosts",1)
        self.debug = kwargs.pop("debug","")
        self.workdir=kwargs.pop("workdir",MakeRandomDir())
        HostPool.__init__(
            self, nhosts=nhosts,workdir=self.workdir,
            commandexecutor=LocalExecutor(
                debug=self.debug,workdir=self.workdir,
                #workdir=kwargs.pop("workdir",None),
                force_workdir=kwargs.pop("force_workdir",False)),
            debug=self.debug,**kwargs)

def CompactIntList(intlist):
    if len(intlist)==0:
        return ""
    elif len(intlist)==1:
        return str(intlist[0])
    else:
        compact = str(intlist[0]); base = intlist[0]
        if intlist[1]>intlist[0]+1:
            return str(intlist[0])+" "+CompactIntList(intlist[1:])
        else:
            for e in range(1,len(intlist)):
                if intlist[e]>intlist[0]+e:
                    return str(intlist[0])+"-"+str(intlist[e-1])+" "\
                        +CompactIntList(intlist[e:])
            return str(intlist[0])+"-"+str(intlist[-1])

class TaskQueue():
    """Object that does the maintains a list of Task objects.
    This is internally created inside a ``LauncherJob`` object."""
    def __init__(self,**kwargs):
        self.queue = []; self.running = []; self.completed = []; self.aborted = []
        self.maxsimul = 0; self.submitdelay = 0
        self.queuestate = kwargs.pop("queuestate","queuestate")
        self.debugs = kwargs.pop("debug",False)
        self.debug = re.search("queue",self.debugs)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed TaskQueue args: %s" % str(kwargs))
    def isEmpty(self):
        """Test whether the queue is empty and no tasks running"""
        return self.queue==[] and self.running==[]
    def enqueue(self,task):
        """Add a task to the queue"""
        DebugTraceMsg("enqueueing <%s>" % str(task),self.debug,prefix="Queue")
        self.queue.append(task)
    def startQueued(self,hostpool,**kwargs):
        """for all queued, try to find nodes to run it on;
        the hostpool argument is a HostPool object"""
        tqueue = copy.copy(self.queue)
        tqueue.sort( key=lambda x:-x.size )
        max_gap = len(hostpool)
        starttick = kwargs.pop("starttick",0)
        for t in tqueue:
            # go through tasks in descending size
            # if one doesn't fit, skip all of same size
            requested_gap = t.size
            if requested_gap>max_gap:
                continue
            locator = hostpool.request_nodes(requested_gap)
            if locator is not None:
                DebugTraceMsg\
                    (f"starting task <{str(t)}> on locator <{str(locator)}>",
                     self.debug,prefix="Queue")
            else:
                DebugTraceMsg(f"could not find nodes for <{str(t)}>",
                              self.debug,prefix="Queue")
                max_gap = requested_gap-1
                continue
            if self.submitdelay>0:
                time.sleep(self.submitdelay)
            t.start_on_nodes(pool=locator,starttick=starttick)
            hostpool.occupyNodes(locator,t.taskid)
            self.queue.remove(t)
            self.running.append(t)
            self.maxsimul = max(self.maxsimul,len(self.running))
    def find_recently_completed(self):
        """Find the first recently completed task.
        Note the return, not yield.
        """
        for t in self.running:
            if t.hasCompleted():
                DebugTraceMsg(".. job completed: %d" % t.taskid,
                              self.debug,prefix="Queue")
                return t
        return None
    def find_recently_aborted(self,abort_test):
        """Find the first recently aborted task.
        Note the return, not yield.
        """
        for t in self.running:
            if abort_test(t):
                DebugTraceMsg(".. job aborted: %d ran from %d" \
                                  % (t.taskid,t.starttick),
                              self.debug,prefix="Queue")
                return t
        return None
    def __repr__(self):
        completed = sorted( [ t.taskid for t in self.completed ] )
        aborted = sorted( [ t.taskid for t in self.aborted] )
        queued = sorted( [ t.taskid for t in self.queue] )
        running = sorted( [ t.taskid for t in self.running ] )
        return \
"""\
completed %3d jobs: %s
aborted   %3d jobs: %s
queued    %3d jobs: %s
running   %3d jobs: %s
""" % ( \
        len(completed),str( CompactIntList(completed) ),
        len(aborted),str( CompactIntList(aborted) ),
        len(queued),str( CompactIntList(queued) ),
        len(running),str( CompactIntList(running) ),
      )
    def savestate(self):
        state = ""
        state += "queued\n"
        for t in self.queue:
            state += "%s: %s\n" % (t.taskid,t.command)
        state += "running\n"
        for t in self.running:
            state += "%s: %s\n" % (t.taskid,t.command)
        state += "completed\n"
        for t in self.completed:
            state += "%s: %s\n" % (t.taskid,t.command)
        return state
    def final_report(self,runningtime):
        """Return a string describing the max and average runtime for each task."""
        times = [ t.runningtime for t in self.completed]
        message = """# tasks completed: %d
tasks aborted: %d
max runningtime: %6.2f
avg runningtime: %6.2f
aggregate      : %6.2f
speedup        : %6.2f
""" % ( len(self.completed), len(self.aborted),
        max( times ), sum( times )/len(self.completed),
        sum( times ), sum( times )/runningtime,
    )
        return message

class TaskGenerator():
    """iterator class that can yield the following:

    * a Task instance, or 
    * the keyword ``stall``; this indicates that the commandline generator is stalling and this will be resolved when the outer environment does an ``append`` on the commandline generator.
    * the ``pylauncherBarrierString``; in this case the outer environment should not call the generator until all currently running tasks have concluded.
    * the keyword ``stop``; this means that the commandline generator is exhausted. The ``next`` function can be called repeatedly on a stopped generator.

    You can iterate over an instance, or call the ``next`` method. The ``next`` method
    can accept an imposed taskcount number.

    :param taskclass: (required keyword) something that derives from Task
    :param commandlinegenerator: either a list of unix commands, or a CommandlineGenerator object
    :param completion: (optional) a function of one variable (the task id) that returns Completion objects
    :param debug: (optional) string of requested debug modes
    :param skip: (optional) list of tasks to skip, this is for restarted jobs

    """
    def __init__(self,commandlines,**kwargs):
        if isinstance(commandlines,(list)):
            self.commandlinegenerator = ListCommandlineGenerator(list=commandlines)
        elif isinstance(commandlines,(CommandlineGenerator)):
            self.commandlinegenerator = commandlines
        else:
            raise LauncherException("Invalid commandline generator object")

        self.taskclass = kwargs.pop("taskclass")
        ## completion can probably go: the completion is set by the 
        ## specific taskclass
        self.workdir = kwargs.pop("workdir",None)
        self.completion = kwargs.pop\
            ("completion",lambda x:Completion(taskid=x,workdir=self.workdir))

        self.taskcount = 0; self.paused = False
        self.debugs = kwargs.pop("debug","")
        self.debug = re.search("task",self.debugs)
        self.skip = kwargs.pop("skip",[])
        if len(kwargs)>0:
            raise LauncherException("Unprocessed TaskGenerator args: %s" % str(kwargs))
    def next(self,imposedcount=None):
        """Deliver a Task object, or a special string:

        * "stall" : the commandline generator will give more, all in good time
        * "stop" : we are totally done
        """
        comm = self.commandlinegenerator.next()
        command = comm["command"]
            # DebugTraceMsg("commandline generator ran out",
            #               self.debug,prefix="Task")
            # command = "stop"
        if command in ["stall","stop"]:
            # the dynamic commandline generator is running dry
            return command
        elif command==pylauncherBarrierString:
            # this is not working yet
            return command
        else:
            if imposedcount is not None:
                taskid = imposedcount
            else:
                taskid = self.taskcount
            self.taskcount += 1
            if taskid in self.skip:
                return self.next(imposedcount=imposedcount)
            else:
                DebugTraceMsg(f"task generator next: id={taskid}",
                              self.debug,prefix="Task")
                return self.taskclass\
                    (comm,taskid=taskid,debug=self.debugs,
                     workdir = self.workdir,
                    )
    def __iter__(self): return self

class WrappedTaskGenerator(TaskGenerator):
    def __init__(self,commandlines,**kwargs):
        TaskGenerator.__init__(self,commandlines,taskclass=WrappedTask,**kwargs)
class BareTaskGenerator(TaskGenerator):
    def __init__(self,commandlines,**kwargs):
        TaskGenerator.__init__(self,commandlines,taskclass=BareTask,**kwargs)

def TaskGeneratorIterate( gen ):
    """In case you want to iterate over a TaskGenerator, use this generator routine"""
    while True:
        t = gen.next()
        if t=="stop":
            raise StopIteration
        yield t

def environment_list():
    """This function takes a command and turns it into
    
    ``cd workdir ; env [the current environment] command``

    Note: environment variables with a space, semicolon, or parentheses
    are not transferred.

    :param command: a unix command, including semicolons and whatnot
    :param workdir: if this is None, the ssh connection will cd to the current directory, otherwise it will go to this workdir. If this is a relative path, it is taken relative to the current directory.
    """
    listcommand = "cd %s\n" % os.environ["PWD"]

    for e in os.environ:
        val = os.environ[e]
        #val = re.sub('\(','\(',val); val = re.sub('\)','\)',val)
        if not re.search("[; ()]",val) and not re.search("command-variables",val) :
            listcommand += "export %s=\"%s\"\n" % (e,val)
    return listcommand

class Executor():
    """Class for starting a commandline on some actual computing device.

    All derived classes need to define a ``execute`` method.

    :param catch_output: (keyword, optional, default=True) state whether command output gets caught, or just goes to stdout
    :param workdir: required, directory for exec and out files
    :parame numa_ctl: (optional) numa binding. Only supported "core" for SSH executor.
    :param debug: (optional) string of debug modes; include "exec" to trace this class

    Important note: the ``workdir`` should not already exist. You have to remove it yourself.
    """
    execstring = "exec"
    outstring = "out"
    def __init__(self,**kwargs):
        self.debugs = kwargs.pop("debug","")
        self.debug = re.search("exec",self.debugs)
        self.catch_output = kwargs.pop("catch_output",True)
        if self.catch_output:
            self.append_output = kwargs.pop("append_output",None)
        self.count = 0
        self.numactl = kwargs.pop("numactl",None)
        if workdir := kwargs.pop("workdir",None):
            print( f"explicit workdir: <<{workdir}>>" )
            self.workdir = workdir
            if self.workdir[0]!="/":
                self.workdir = os.getcwd()+"/"+self.workdir
            DebugTraceMsg("Using executor workdir <<%s>>" % self.workdir,
                          self.debug,prefix="Exec")
            if os.path.isdir(self.workdir):
                print( f"Implementor warning: re-using workdir <<{self.workdir}>>" )
            elif os.path.isfile(self.workdir):
                raise LauncherException( f"Workdir <<{self.workdir}>> should not be a file" )
            else:
                os.mkdir(self.workdir)
        else:
            raise LauncherException("Executor needs explicit workdir")
        if len(kwargs)>0:
            raise LauncherException("Unprocessed Executor args: %s" % str(kwargs))
    def workdir_is_safe(self):
        """Test that the working directory is (in) a subdirectory of the cwd"""
        here = os.getcwd(); os.chdir(self.workdir); there = os.getcwd(); os.chdir(here)
        return re.match(here,there) and not here==there
    def cleanup(self):
        if self.workdir_is_safe():
            shutil.rmtree(self.workdir)
    def setup_on_node(self,node):
        return
    def release_from_node(self,node):
        return
    def end_execution(self):
        return
    def smallfilenames(self):
        execfilename = "%s/%s%d" % (self.workdir,self.execstring,self.count)
        if self.catch_output:
            if self.append_output is not None:
                execoutname = self.append_output
            else: 
                execoutname =  "%s/%s%d" % (self.workdir,self.outstring,self.count)
        else:
            execoutname = ""
        self.count += 1
        return execfilename,execoutname
    def wrap(self,command,prefix=""):
        """Take a commandline, write it to a small file, and return the 
        commandline that sources that file
        """
        execfilename,execoutname = self.smallfilenames()
        if os.path.isfile(execfilename):
            raise LauncherException("exec file already exists <<%s>>" % execfilename)
        f = open(execfilename,"w")
        f.write("#!/bin/bash\n"+command+"\n")
        f.close()
        os.chmod(execfilename,stat.S_IXUSR++stat.S_IXGRP+stat.S_IXOTH+\
                     stat.S_IWUSR++stat.S_IWGRP+stat.S_IWOTH+\
                     stat.S_IRUSR++stat.S_IRGRP+stat.S_IROTH)
        if self.catch_output:
            if self.append_output is not None:
                pipe = ">>"
            else: 
                pipe = ">"
            wrappedcommand = "%s %s %s 2>&1" % (execfilename,pipe,execoutname)
        else:
            wrappedcommand = execfilename
        wrappedcommand = prefix+wrappedcommand
        DebugTraceMsg("commandline <<%s>>" % wrappedcommand,
                      self.debug,prefix="Exec")
        return wrappedcommand
    def execute(self,command,**kwargs):
        raise LauncherException("Should not call default execute")
    def terminate(self):
        return

class LocalExecutor(Executor):
    """Execute a commandline locally, in the background.

    :param prefix: (keyword, optional, default null string) for recalcitrant shells, the possibility to specify '/bin/sh' or so
    """
    def __init__(self,**kwargs):
        self.prefix = kwargs.pop("prefix","")
        Executor.__init__(self,**kwargs)
        DebugTraceMsg("Created local Executor",self.debug,prefix="Exec")
    def execute(self,command,**kwargs):
        wrapped = self.wrap(command)
        fullcommandline = "%s%s & " % (self.prefix,wrapped)
        DebugTraceMsg("subprocess execution of:\n<<%s>>" % fullcommandline,
                      self.debug,prefix="Exec")
        p = subprocess.Popen(fullcommandline,shell=True,env=os.environ,
                             stderr=subprocess.STDOUT)
        # !!! why that os.environ and the env prefix?

def ssh_client(host,debug=False):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if debug:
        print("Create paramiko ssh client to",host,flush=True)
    ssh.connect(host)
    return ssh

class SSHExecutor(Executor):
    """Intelligent ssh connection.
    
    This is either a new paramiko ssh connection or a copy of an existing one,
    so that we don't open multiple connections to one node.

    Commands are executed with:
    ``cd`` to the current directory, and 
    copy the current environment. 

    Note: environment variables with a space, semicolon, or parentheses
    are not transferred.

    For parameters, see the Executor class.
    """
    def __init__(self,**kwargs):
        self.node_client_dict = {}
        self.debugs = kwargs.pop("debug","")
        Executor.__init__(self,debug=self.debugs,**kwargs)
        self.debug = self.debug or re.search("ssh",self.debugs)
        DebugTraceMsg("Created SSH Executor",self.debug,prefix="Exec")
    def setup_on_node(self,node):
        host = node.hostname
        DebugTraceMsg( f"Set up connection to {host}",self.debug,prefix="SSH")
        if host in self.node_client_dict:
            node.ssh_client = self.node_client_dict[host]
            node.ssh_client_unique = False
        else:
            DebugTraceMsg( f"making ssh client to host: {host}",self.debug,prefix="SSH")
            try : 
                node.ssh_client = ssh_client(host,debug=self.debug)
            except: ## VLE is this an exception class? socket.gaierror as e:
                print( f"\nParamiko could not create ssh client to {host}\n",flush=True)
            node.ssh_client_unique = True
            self.node_client_dict[host] = node.ssh_client
    def release_from_node(self,node):
        if node.ssh_client_unique:
            node.ssh_client.close()
    def execute(self,usercommand,**kwargs):
        """Execute a commandline in the background on the ssh_client object
        in this Executor object.

        * usercommand gets the environment prefixed to it
        * result is wrapped with Executor.wrap

        :param pool: (required) either a Node or HostLocator
        """
        # find where to execute
        pool = kwargs.pop("pool",None)
        if pool is None:
            raise LauncherException("SSHExecutor needs explicit HostPool")
        if isinstance(pool,(Node)):
            hostname = pool.hostname
        elif isinstance(pool,(HostLocator)):
            hostname = pool.firsthost()
        else:
            raise LauncherException("Invalid pool <<%s>>" % str(pool))
        if self.numactl is None:
            exec_prefix = ""
        elif self.numactl=="core":
            cores = pool.first_range()
            exec_prefix = "numactl -C %s " % cores
        elif self.numactl=="gpu":
            cores = pool.first_range()
            exec_prefix = "CUDA_VISIBLE_DEVICES=%s " % cores
        else:
            raise LauncherException("Unknown numactl: %s" % self.numactl)
        # construct the command line with environment, workdir and expiration
        env_line = environment_list()
        wrapped_line = self.wrap(env_line+usercommand+"\n",prefix=exec_prefix)
        DebugTraceMsg("Executing << ( %s ) & >> on <<%s>>" % (wrapped_line,hostname),
                      self.debug,prefix="SSH")
        ssh = self.node_client_dict[hostname]
        try:
            stdin,stdout,stderr = ssh.exec_command("( %s ) &" % wrapped_line)
        except : # old paramiko value? ChannelException:
            DebugTraceMsg("Channel exception; let's see if this blows over",prefix="SSH")
            time.sleep(3)
            ssh.exec_command("( %s ) &" % wrapped_line)
    def end_execution(self):
        self.session.send('\x03')
        self.session.close()

class SubmitExecutor(Executor):
    """Execute a commandline by wrapping it in a slurm script
    Not elegant: we have to specify BareCompletion both here
    and in the task generator.
    """
    def __init__(self,submitparams,**kwargs):
        self.submitparams = submitparams
        Executor.__init__(self,**kwargs)
        DebugTraceMsg("Created Slurm Submit Executor",self.debug,prefix="Exec")
    def execute(self,command,**kwargs):
        id = kwargs.pop("id","0")
        completion_function = lambda x:WrapCompletion(taskid=x,workdir=self.workdir)
        completion = completion_function(id)
        command_and_stamp = completion.attach(command)
        scriptname = f"{self.workdir}/jobscript{id}"
        with open( scriptname , "w" ) as jobscript:
            jobscript.write(
f"""#!/bin/bash
#SBATCH -o launcherjob.out
#SBATCH -e launcherjob.out
{command_and_stamp}
""")
        fullcommandline = f"sbatch {self.submitparams} {scriptname}"
        DebugTraceMsg("subprocess execution of:\n<<%s>>" % fullcommandline,
                      self.debug,prefix="Exec")
        p = subprocess.Popen(fullcommandline,shell=True,env=os.environ,
                             stderr=subprocess.STDOUT)

class MPIExecutor(Executor):
    """An Executor derive class for a generic mpirun
    
    : param pool: (requires) ``HostLocator`` object
    : param stdout: (optional) a file that is opne for writing; by default ``subprocess.PIPE`` is used
    
    """
    def __init__(self,**kwargs):
        catch_output = kwargs.pop("catch_output","foo")
        if catch_output != "foo": 
            raise LauncherException("MPIExecutor does not take catch_output parameter.")
        self.hfswitch = kwargs.pop("hfswitch","-machinefile")
        Executor.__init__(self,catch_output=False,**kwargs)
        self.popen_object = None
    def execute(self,command,**kwargs):
        '''Because we do not have all the work that ibrun does on TACC systems, we will have 
        handle more parts.
        We need to define a hostfile for the correct subset of the nodes,
        '''
        # find where to execute
        pool = kwargs.pop("pool",None)
        if pool is None:
            raise LauncherException("SSHExecutor needs explicit HostPool")
        stdout = kwargs.pop("stdout",subprocess.PIPE)
        # construct the command line with environment, workdir, and expiration
        # Construct a hostlist for use by mpirun
        np = pool.extent
        machinelist = list()
        for i in range(int(pool.offset),(int(pool.offset)+int(pool.extent))):
            machinelist.append(pool.pool.nodes[i].hostname)
        stdout = kwargs.pop("stdout",subprocess.PIPE)
        #hfswitch = kwargs.pop("hfswitch","-machinefile")
        hostfilename = 'hostfile.'
        hostfilenumber = 0
        while os.path.exists(os.path.join(self.workdir,hostfilename+str(hostfilenumber))):
            hostfilenumber += 1
        with open(os.path.join(self.workdir,hostfilename+str(hostfilenumber)),'w') as myhostfile:
            for machine in machinelist:
                myhostfile.write(machine+'\n')
        full_commandline = "mpirun -np {0} {1} {2} {3} ".format(np,self.hfswitch,os.path.join(self.workdir,hostfilename+str(hostfilenumber)),self.wrap(command))
        DebugTraceMsg("executed commandline: <<%s>>" % full_commandline, self.debug,prefix="Exec")
        p = subprocess.Popen(full_commandline,shell=True,stdout=stdout)
        self.popen_object = p
    def terminate(self):
        if self.popen_object is not None:
            self.popen_object.terminate()



class IbrunExecutor(Executor):
    """An Executor derived class for the shift/offset version of ibrun
    that is in use at TACC

    :param pool: (required) ``HostLocator`` object
    :param stdout: (optional) a file that is open for writing; by default ``subprocess.PIPE`` is used
    """
    def __init__(self,**kwargs):
        catch_output = kwargs.pop("catch_output","foo")
        if catch_output!="foo":
            raise LauncherException("IbrunExecutor does not take catch_output parameter")
        Executor.__init__(self,catch_output=False,**kwargs)
        self.popen_object = None
    def execute(self,command,**kwargs):
        """Much like ``SSHExecutor.execute()``, except that it prefixes
        with ``ibrun -n -o``
        """
        pool = kwargs.pop("pool",None)
        if pool is None:
            raise LauncherException("SSHExecutor needs explicit HostPool")
        wrapped_command = self.wrap(command)
        stdout = kwargs.pop("stdout",subprocess.PIPE)
        full_commandline \
            = [ "ibrun","-o",str(pool.offset),"-n",str(pool.extent),
                wrapped_command ] # not: "&"
        full_commandline \
            =  "ibrun -o %d -n %d %s" % \
               (pool.offset,pool.extent,wrapped_command)
        DebugTraceMsg("executed commandline: <<%s>>" % str(full_commandline),
                      self.debug,prefix="Exec")
        p = subprocess.Popen(full_commandline,
                             shell=True,
                             stdout=stdout)
        self.popen_object = p
    def terminate(self):
        if self.popen_object is not None:
            self.popen_object.terminate()

class MpiexecExecutor(Executor):
    """An Executor derived class using ordinary mpiexec.

    :param pool: (required) ``HostLocator`` object
    :param stdout: (optional) a file that is open for writing; by default ``subprocess.PIPE`` is used
    """
    def __init__(self,**kwargs):
        catch_output = kwargs.pop("catch_output","foo")
        if catch_output!="foo":
            raise LauncherException("IbrunExecutor does not take catch_output parameter")
        Executor.__init__(self,catch_output=False,**kwargs)
        self.popen_object = None
    def execute(self,command,**kwargs):
        """Much like ``SSHExecutor.execute()``, except that it prefixes
        with ``ibrun -n -o``
        """
        pool = kwargs.pop("pool",None)
        if pool is None:
            raise LauncherException("SSHExecutor needs explicit HostPool")
        wrapped_command = self.wrap(command)
        stdout = kwargs.pop("stdout",subprocess.PIPE)
        # full_commandline \
        #     =  "ibrun -o %d -n %d %s" % \
        #        (pool.offset,pool.extent,wrapped_command)
        full_commandline \
            =  "mpiexec -n %d %s" % \
               (pool.extent,wrapped_command)
        DebugTraceMsg("executed commandline: <<%s>>" % str(full_commandline),
                      self.debug,prefix="Exec")
        p = subprocess.Popen(full_commandline,
                             shell=True,
                             stdout=stdout)
        self.popen_object = p
    def terminate(self):
        if self.popen_object is not None:
            self.popen_object.terminate()

class LauncherJob():
    """LauncherJob class. Keyword arguments:

    :param hostpool: a HostPool instance (required)
    :param taskgenerator: a TaskGenerator instance (required)
    :param delay: between task checks  (optional)
    :param debug: list of keywords (optional)
    :param gather_output: (keyword, optional, default None) filename to gather all command output
    :param maxruntime: (keyword, optional, default zero) if nonzero, maximum running time in seconds
    """
    def __init__(self,**kwargs):
        print( f"Start launcherjob, launcher version: {pylauncher_version}" )
        self.debugs = kwargs.pop("debug","")
        self.debug = re.search("job",self.debugs)
        self.hostpool = kwargs.pop("hostpool",None)
        if self.hostpool is None:
            raise LauncherException("Need a host pool")
        self.workdir = kwargs.pop("workdir",".")
        self.queuestate = self.workdir+"/"+kwargs.pop("queuestate","queuestate")
        DebugTraceMsg("Host pool: <<%s>>" % str(self.hostpool),
                      re.search("host",self.debugs),"Job")
        self.taskgenerator = kwargs.pop("taskgenerator",None)
        if self.taskgenerator is None:
            raise LauncherException("Need a task generator")
        self.delay = kwargs.pop("delay",.5)
        self.queue = TaskQueue(debug=self.debugs)
        self.maxruntime = kwargs.pop("maxruntime",0)
        self.taskmaxruntime = kwargs.pop("taskmaxruntime",0)
        self.completed = 0; self.aborted = 0; self.tock = 0; self.stalling = False
        self.gather_output = kwargs.pop("gather_output",None)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed LauncherJob args: %s" % str(kwargs))
    def finish_or_continue(self):
        # auxiliary routine, purely to make ``tick`` look shorter
        if self.queue.isEmpty():
            if self.completed==0:
                raise LauncherException("Done before we started....")
            DebugTraceMsg("Generator and tasks finished",self.debug,prefix="Job")
            message = "finished"
        else:
            DebugTraceMsg("Generator finished; tasks still running",self.debug,prefix="Job")
            message = "continuing"
        return message
    def enqueue_task(self,task):
        # auxiliary routine, purely to make ``tick`` look shorter
        if not isinstance(task,(Task)):
            raise LauncherException("Not a task: %s" % str(task))
        DebugTraceMsg("enqueueing new task <%s>" % str(task),
                      self.debug,prefix="Job")
        self.queue.enqueue(task)
    def tick(self,monitor):
        """This routine does a single time step in a launcher's life, and reports back
        to the user. Specifically:

        * It tries to start any currently queued jobs. Also:
        * If any jobs are finished, it detects exactly one, and reports its ID to the user in a message ``expired 123``
        * If there are no finished jobs, it invokes the task generator; this can result in a new task and the return message is ``continuing``
        * if the generator stalls, that is, more tasks will come in the future but none are available now, the message is ``stalling``
        * if the generator is finished and all jobs have finished, the message is ``finished``

        After invoking the task generator, a short sleep is inserted (see the ``delay`` parameter)

        :param monitor : monitor routine to be invoked.

        """
        DebugTraceMsg("\ntick %d\nQueue:\n%s" % (self.tock,str(self.queue)),self.debug)
        self.tock += 1

        if not self.stalling:
            # should this line go inside the handle_enqueing?
            self.queue.startQueued(self.hostpool,starttick=self.tock)
        message = None
        self.handle_completed()
        self.handle_aborted()
        message = self.handle_enqueueing()
        monitor() # this can be NullMonitor
        time.sleep(self.delay)

        if re.search("host",self.debugs):
            DebugTraceMsg(str(self.hostpool))
        DebugTraceMsg("status=%s" % message,self.debug,prefix="Job")
        return message
    def handle_completed(self):
        message = None
        completed_task = self.queue.find_recently_completed()
        if not completed_task is None:
            self.queue.running.remove(completed_task)
            self.queue.completed.append(completed_task)
            completeID = completed_task.taskid
            DebugTraceMsg("completed: %d" % completeID,self.debug,prefix="Job")
            self.completed += 1
            self.hostpool.releaseNodesByTask(completeID)
            message = "expired %s" % str(completeID)
        return message
    def handle_aborted(self):
        message = None
        aborted_task = self.queue.find_recently_aborted(
            lambda t:self.taskmaxruntime>0 and self.tock-t.starttick>self.taskmaxruntime )
        if not aborted_task is None:
            self.queue.running.remove(aborted_task)
            self.queue.aborted.append(aborted_task)
            completeID = aborted_task.taskid
            DebugTraceMsg("aborted: %d" % completeID,self.debug,prefix="Job")
            self.aborted += 1
            self.hostpool.releaseNodesByTask(completeID)
            message = "truncated %s" % str(completeID)
        return message
    def handle_enqueueing(self):
        message = None
        barriertasks = [ t.completion for t in self.queue.running ]
        ntogo = len(barriertasks)
        if self.stalling:
            if ntogo==0: 
                self.stalling = False
                DebugTraceMsg("barrier resolved".format(ntogo),
                              self.debug,prefix="Job")
                message = "continuing"
            else:
                DebugTraceMsg("still in barrier: {} tasks to go".format(ntogo),
                              self.debug,prefix="Job")
                message = "stalling"
        else:
            task = self.taskgenerator.next()
            if task==pylauncherBarrierString:
                self.stalling = True
                DebugTraceMsg("barrier encountered; {} tasks to go".format(ntogo),
                              self.debug,prefix="Job")
                message = "stalling"
            elif task=="stall":
                message = "stalling"
                DebugTraceMsg("stalling",self.debug,prefix="Job")
            elif task=="stop":
                message = self.finish_or_continue()
                DebugTraceMsg("rolling till completion",self.debug,prefix="Job")
            else:
                self.enqueue_task(task)
                message = "enqueueing"
            # except: message = self.finish_or_continue()
        return message
    def post_process(self,taskid):
        DebugTraceMsg("Task %s expired" % str(taskid),self.debug,prefix="Job")
    def run(self,**kwargs):
        """Invoke the launcher job, and call ``tick`` until all jobs are finished."""
        monitor = kwargs.pop("monitor",NullMonitor)
        if re.search("host",self.debugs):
            self.hostpool.printhosts()
        self.starttime = time.time()
        while True:
            elapsed = time.time()-self.starttime
            runtime = "Time: %d" % int(elapsed)
            if self.maxruntime>0:
                runtime += " (out of %d)" % int(self.maxruntime)
            DebugTraceMsg(runtime,self.debug,prefix="Job")
            if self.maxruntime>0:
                if elapsed>self.maxruntime:
                    break
            res = self.tick(monitor)
            # update restart file
            queuestate_update(self.queuestate,self.queue.savestate())
            if res=="finished":
                break
        self.runningtime = time.time()-self.starttime
        self.finish()
    def finish(self):
        self.hostpool.release()
    def final_report(self):
        """Return a string describing the total running time, as well as
        including the final report from the embedded ``HostPool`` and ``TaskQueue``
        objects."""
        message = """
==========================
Launcherjob run completed.

total running time: %6.2f

%s

%s
==========================
""" % ( self.runningtime, self.queue.final_report(self.runningtime),
        self.hostpool.final_report() )
        return message
def queuestate_update( queuestate,savestate ):
    ## update the restart file
    ## first create recursive directories if needed
    qdir = re.sub( r'[^/]+$','',queuestate)
    os.makedirs(qdir,exist_ok=True)
    state_f = open(queuestate,"w")        
    state_f.write( savestate )
    state_f.close()
def NullMonitor():
    pass
def SlurmSqueueMonitor():
    squeuecommandline = f"squeue -u {os.environ['USER']}"
    p = subprocess.Popen(squeuecommandline,shell=True,env=os.environ,
                         stderr=subprocess.STDOUT)


def ClassicLauncher(commandfile,*args,**kwargs):
    """A LauncherJob for a file of single or multi-threaded commands.

    The following values are specified for your convenience:

    * hostpool : based on HostListByName
    * commandexecutor : SSHExecutor
    * taskgenerator : based on the ``commandfile`` argument
    * completion : based on a directory ``pylauncher_tmp`` with jobid environment variables attached

    :param commandfile: name of file with commandlines (required)
    :param resume: if 1,yes interpret the commandfile as a queuestate file
    :param cores: number of cores per commandline (keyword, optional, default=1)
    :param corespernode: mostly for weird KNL core numbering
    :param workdir: (keyword, optional, default=pylauncher_tmp_jobid) directory for output and temporary files; the launcher refuses to reuse an already existing directory
    :param debug: debug types string (optional, keyword)
    """
    jobid = JobId()
    debug = kwargs.pop("debug","")
    workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
    cores = kwargs.pop("cores",1)
    corespernode = kwargs.pop("corespernode",None)
    numactl = kwargs.pop("numactl",None)
    resume = kwargs.pop("resume",None)
    if resume is not None and not (resume=="0" or resume=="no"):
        generator = StateFileCommandlineGenerator(commandfile,cores=cores,debug=debug)
    else:
        generator = FileCommandlineGenerator(commandfile,cores=cores,debug=debug)
    commandexecutor = SSHExecutor(workdir=workdir,numactl=numactl,debug=debug)
    job = LauncherJob(
        hostpool=HostPool(
            hostlist=HostListByName\
                (commandexecutor=commandexecutor,workdir=workdir,
                 corespernode=corespernode,debug=debug),
            commandexecutor=commandexecutor,workdir=workdir,
            debug=debug ),
        taskgenerator=WrappedTaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            workdir=workdir, debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print(job.final_report(),flush=True)

def LocalLauncher(commandfile,nhosts,*args,**kwargs):
    """A LauncherJob for a file of single or multi-threaded commands, running locally

    The following values are specified for your convenience:

    * hostpool : based on HostListByName
    * commandexecutor : SSHExecutor
    * taskgenerator : based on the ``commandfile`` argument
    * completion : based on a directory ``pylauncher_tmp`` with jobid environment variables attached

    :param commandfile: name of file with commandlines (required)
    :param resume: if 1,yes interpret the commandfile as a queuestate file
    :param cores: number of cores (keyword, optional, default=1)
    :param workdir: (keyword, optional, default=pylauncher_tmp_jobid) directory for output and temporary files; the launcher refuses to reuse an already existing directory
    :param debug: debug types string (optional, keyword)
    """
    jobid = JobId()
    debug = kwargs.pop("debug","")
    workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
    cores = kwargs.pop("cores",1)
    resume = kwargs.pop("resume",None)
    if resume is not None and not (resume=="0" or resume=="no"):
        generator = StateFileCommandlineGenerator(commandfile,cores=cores,debug=debug)
    else:
        generator = FileCommandlineGenerator(commandfile,cores=cores,debug=debug)
    job = LauncherJob(
        hostpool=LocalHostPool( nhosts=nhosts ),
        taskgenerator=WrappedTaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            completion=lambda x:FileCompletion\
                ( taskid=x,workdir=workdir),
            workdir=workdir, debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print(job.final_report(),flush=True)

def ResumeClassicLauncher(commandfile,**kwargs):
    ClassicLauncher(commandfile,resume=1,**kwargs)

def MPILauncher(commandfile,**kwargs):
    '''A LauncherJob for a file of small MPI jobs, for a system not using Ibrun
    
    The following values are specified using other functions.

    * hostpool : determined via HostListByName
    * commandexecutor : MPIExecutor
    * taskgenerator : based on the ``commandfile`` argument
    * complete : based on a diretory ``pylauncher_tmp`` with jobid environment variables attached

    :param commandfile: name of files with commandlines (required)
    :param cores: number of cores (keyword, optional, default=4, see ``FileCommandlineGenerator`` for more explanation)
    :param workdir: directory for output and temporary files (optional, keyword, default uses the job number); the launcher refuses to resuse an already existing directory
    :param debug: debug types string (optional, keyword)
    :param hfswitch: Switch used to determine the hostifle switch used with your MPI distribution. Default is -machinefile (optional,keyword)
    '''
    jobid = JobId()
    debug = kwargs.pop("debug","")
    workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
    cores =  kwargs.pop("cores",4)
    hfswitch = kwargs.pop("hfswitch","-machinefile")
    job = LauncherJob(
        hostpool=HostPool( hostlist=HostListByName(),
            commandexecutor=MPIExecutor(workdir=workdir,debug=debug,hfswitch=hfswitch), debug=debug ),
        taskgenerator=WrappedTaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            completion=lambda x:FileCompletion\
                (taskid=x,workdir=workdir),
            workdir=workdir, debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print(job.final_report(),flush=True)

def IbrunLauncher(commandfile,**kwargs):
    """A LauncherJob for a file of small MPI jobs.

    The following values are specified for your convenience:

    * hostpool : based on HostListByName
    * commandexecutor : IbrunExecutor
    * taskgenerator : based on the ``commandfile`` argument
    * completion : based on a directory ``pylauncher_tmp`` with jobid environment variables attached

    :param commandfile: name of file with commandlines (required)
    :param cores: number of cores (keyword, optional, default=4, see ``FileCommandlineGenerator`` for more explanation)
    :param workdir: directory for output and temporary files (optional, keyword, default uses the job number); the launcher refuses to reuse an already existing directory
    :param debug: debug types string (optional, keyword)
    """
    jobid = JobId()
    debug = kwargs.pop("debug","")
    workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
    cores = kwargs.pop("cores",4)
    job = LauncherJob(
        hostpool=HostPool( hostlist=HostListByName(debug=debug),
            commandexecutor=IbrunExecutor(workdir=workdir,debug=debug), debug=debug ),
        taskgenerator=WrappedTaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            completion=lambda x:FileCompletion\
                (taskid=x,workdir=workdir),
            workdir=workdir, debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print(job.final_report(),flush=True)

def GPULauncher(commandfile,**kwargs):
    """A LauncherJob for a file of small MPI jobs.

    The following values are specified for your convenience:

    * hostpool : based on HostListByName
    * commandexecutor : GPUExecutor
    * taskgenerator : based on the ``commandfile`` argument
    * completion : based on a directory ``pylauncher_tmp`` with jobid environment variables attached

    :param commandfile: name of file with commandlines (required)
    :param cores: number of cores (keyword, optional, default=4, see ``FileCommandlineGenerator`` for more explanation)
    :param workdir: directory for output and temporary files (optional, keyword, default uses the job number); the launcher refuses to reuse an already existing directory
    :param debug: debug types string (optional, keyword)
    """
    jobid = JobId()
    debug = kwargs.pop("debug","")
    workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
    cores = kwargs.pop("cores",1)
    job = LauncherJob(
        hostpool=HostPool( hostlist=HostListByName(debug=debug),
            commandexecutor=SSHExecutor\
                (numactl="gpu", workdir=workdir ,debug=debug),             
            workdir=workdir, debug=debug ),
        taskgenerator=WrappedTaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            completion=lambda x:FileCompletion(taskid=x,workdir=workdir),
            workdir=workdir, debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print(job.final_report(),flush=True)

def RemoteLauncher(commandfile,hostlist,**kwargs):
    """A LauncherJob for a file of single or multi-thread commands, executed remotely.

    The following values are specified for your convenience:

    * commandexecutor : IbrunExecutor
    * taskgenerator : based on the ``commandfile`` argument
    * completion : based on a directory ``pylauncher_tmp`` with jobid environment variables attached

    :param commandfile: name of file with commandlines (required)
    :param hostlist : list of hostnames
    :param cores: number of cores (keyword, optional, default=4, see ``FileCommandlineGenerator`` for more explanation)
    :param workdir: directory for output and temporary files (optional, keyword, default uses the job number); the launcher refuses to reuse an already existing directory
    :param debug: debug types string (optional, keyword)
    """
    jobid = "000"
    debug = kwargs.pop("debug","")
    workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
    ppn = kwargs.pop("ppn",4)
    cores = kwargs.pop("cores",1)
    job = LauncherJob(
        hostpool=HostPool( 
            hostlist=ListHostList(hostlist,ppn=ppn,debug=debug),
            commandexecutor=SSHExecutor(workdir=workdir,debug=debug), 
            workdir=workdir, debug=debug ),
        taskgenerator=WrappedTaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            completion=lambda x:FileCompletion(taskid=x,workdir=workdir),
            workdir=workdir, debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print(job.final_report(),flush=True)

def SubmitLauncher(commandfile,submitparams,**kwargs):
    """A LauncherJob for a file of single or multi-thread commands, executed remotely.

    The following values are specified for your convenience:

    * commandexecutor : SubmitExecutor
    * taskgenerator : based on the ``commandfile`` argument
    * completion : based on a directory ``pylauncher_tmp`` with jobid environment variables attached

    :param commandfile: name of file with commandlines (required)
    :param nactive : maximum number of submissions to be active simultaneously
    :param cores: number of cores (keyword, optional, default=4, see ``FileCommandlineGenerator`` for more explanation)
    :param workdir: directory for output and temporary files (optional, keyword, default uses the job number); the launcher refuses to reuse an already existing directory
    :param debug: debug types string (optional, keyword)
    """
    jobid = "000"
    debug = kwargs.pop("debug","")
    nactive = kwargs.pop("nactive",1)
    queue = kwargs.pop("queue","normal")
    workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
    cores = kwargs.pop("cores",1)
    if debug:
        monitor = SlurmSqueueMonitor
    else: monitor = NullMonitor
    job = LauncherJob(
        hostpool=HostPool( 
            hostlist=ListHostList(
                [queue for a in range(nactive)], debug=debug),
            commandexecutor=SubmitExecutor(
                submitparams, workdir=workdir, debug=debug),
            workdir=workdir, debug=debug ),
        taskgenerator=BareTaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            workdir=workdir, debug=debug ),
        debug=debug,**kwargs)
    job.run(monitor=monitor)
    print(job.final_report(),flush=True)

def RemoteIbrunLauncher(commandfile,hostlist,**kwargs):
    """A LauncherJob for a file of small MPI jobs, executed remotely.

    The following values are specified for your convenience:

    * commandexecutor : IbrunExecutor
    * taskgenerator : based on the ``commandfile`` argument
    * completion : based on a directory ``pylauncher_tmp`` with jobid environment variables attached

    :param commandfile: name of file with commandlines (required)
    :param hostlist : list of hostnames
    :param cores: number of cores (keyword, optional, default=4, see ``FileCommandlineGenerator`` for more explanation)
    :param workdir: directory for output and temporary files (optional, keyword, default uses the job number); the launcher refuses to reuse an already existing directory
    :param debug: debug types string (optional, keyword)
    """
    jobid = 000
    debug = kwargs.pop("debug","")
    workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
    ppn = kwargs.pop("ppn",4)
    cores = kwargs.pop("cores",4)
    job = LauncherJob(
        hostpool=HostPool( 
            hostlist=ListHostList(hostlist,ppn=ppn,debug=debug),
            commandexecutor=SSHExecutor(workdir=workdir,debug=debug), debug=debug ),
        taskgenerator=WrappedTaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            completion=lambda x:FileCompletion(taskid=x,workdir=workdir),
            workdir=workdir, debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print(job.final_report(),flush=True)

class DynamicLauncher(LauncherJob):
    """A LauncherJob derived class that is designed for dynamic adding of 
    commands. This should make it easier to integrate
    in environments that expect to "submit" jobs one at a time.

    This has two extra methods:
    * append(commandline) : add commandline to the internal queueu
    * none_waiting() : check that all commands are either running or finished

    Optional parameters have a default value that makes it behave like
    the ClassicLauncher.

    :param hostpool: (optional) by default based on HostListByName())
    :
    """
    def __init__(self,**kwargs):
        jobid = kwargs.pop("jobid",JobId())
        debug = kwargs.pop("debug","")
        hostpool = kwargs.pop("hostpool",
            HostPool( hostlist=HostListByName(debug=debug),
                      commandexecutor=SSHExecutor(workdir=workdir,debug=debug), 
                      debug=debug ))
        workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
        cores = kwargs.pop("cores",1)
        LauncherJob.__init__(self,
            hostpool=hostpool,
            taskgenerator=WrappedTaskGenerator( 
                DynamicCommandlineGenerator(commandfile,cores=cores,debug=debug),
                completion=lambda x:FileCompletion( taskid=x,workdir=workdir),
                workdir=workdir, debug=debug ),
            debug=debug,**kwargs)
    def append(self,commandline):
        """Append a Unix commandline to the generator"""
        self.taskgenerator.append( Commandline(commandline) )
    def none_waiting(self):
        return len(self.queue.queue)==0

def MICLauncher(commandfile,**kwargs):
    """A LauncherJob for execution entirely on an Intel Xeon Phi.

    See ``ClassicLauncher`` for an explanation of the parameters.
    The only difference is in the use of a LocalExecutor.
    Treatment of the MIC cores is handled in the ``HostListByName``.
    """
    jobid = JobId()
    debug = kwargs.pop("debug","")
    workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
    cores = kwargs.pop("cores",1)
    job = LauncherJob(
        hostpool=HostPool( hostlist=HostListByName(debug=debug),
            commandexecutor=LocalExecutor(
                prefix="/bin/sh ",workdir=workdir,debug=debug), 
                           debug=debug ),
        taskgenerator=WrappedTaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            completion=lambda x:FileCompletion( taskid=x,workdir=workdir),
            workdir=workdir, debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print(job.final_report(),flush=True)

os.environ["PYLAUNCHER_ENABLED"] = "1"

