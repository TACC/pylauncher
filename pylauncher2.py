docstring = \
"""pylauncher.py version 3.2

A python based launcher utility for packaging sequential or
low parallel jobs in one big parallel job

Author: Victor Eijkhout
eijkhout@tacc.utexas.edu
Modifications for PBS-based systems: Christopher Blanton
chris.blanton@gatech.edu
"""

changelog = """
Change log
3.2
- Semeraro fixes for Frontera
3.0
- remove 6999 port after ls5 upgrade
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
import hostlist as hs


class LauncherException(Exception):
    """A very basic exception mechanism"""
    def __init__(self,str):
        print str
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
        print longprefix+l
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
    print "using random dir:",dirname
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

def testCountedCommandGenerator():
    ntasks = 15
    generator = CountedCommandGenerator(nmax=ntasks)
    count = 0
    for g in generator:
        assert( re.match('echo',g) )
        count += 1
    assert(count==ntasks)

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

def testSleepWait():
    wait5 = SingleSleepCommand(3,tmin=3)
    start = time.time()
    os.system(wait5)
    duration = time.time()-start
    assert( duration>2.5 )
    assert( duration<4 )

def testSleepCommandGenerator():
    ntasks = 15; tmax = 7
    generator = SleepCommandGenerator(nmax=ntasks,tmax=tmax)
    count = 0
    for g in generator:
        gs = g.split(); print gs
        # echo i 2>&1 > /dev/null ; sleep t
        # 0    1 2    3 4         5 6     7
        assert( int(gs[1])==count and int(gs[7])<=tmax )
        count += 1
    assert(count==ntasks)

def testSleepCommandGeneratorBarrier():
    """testSleepCommandGeneratorBarrier: test that we insert barriers"""
    ntasks = 15; tmax = 7; barrier_interval = 3
    nbarrier = math.ceil( ntasks/barrier_interval )
    generator = SleepCommandGenerator(nmax=ntasks,tmax=tmax,barrier=barrier_interval)
    count = 0; count_barrier = 0
    for g in generator:
        if g==pylauncherBarrierString:
            count_barrier += 1
            print "counted barrier %d after %d lines" % (count_barrier,count)
            assert(count_barrier<=nbarrier)
            continue
        gs = g.split(); print gs
        # echo i 2>&1 > /dev/null ; sleep t
        # 0    1 2    3 4         5 6     7
        assert( int(gs[1])==count and int(gs[7])<=tmax )
        count += 1
    print "tasks:",count
    assert(count==ntasks)
    print "barriers:",count_barrier
    assert(count_barrier==nbarrier)

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
        self.list = [ e for e in kwargs.pop("list",[]) ]; 
        self.ncommands = len(self.list); self.njobs = 0
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
        self.stopped = False
    def finish(self):
        """Tell the generator to stop after the commands list is depleted"""
        DebugTraceMsg("declaring the commandline generator to be finished",
                      self.debug,prefix="Cmd")
        self.nmax = self.njobs+len(self.list)
    def abort(self):
        """Stop the generator, even if there are still elements in the commands list"""
        DebugTraceMsg("gettingthe commandline generator to abort",
                      self.debug,prefix="Cmd")
        self.stopped = True
    def next(self):
        """Produce the next Commandline object, or return an object telling that the
        generator is stalling or has stopped"""
        if self.stopped:
            DebugTraceMsg("stopping the commandline generator",
                          self.debug,prefix="Cmd")
            raise StopIteration
        elif ( len(self.list)==0 and self.nmax!=0 ) or \
                ( self.nmax>0 and self.njobs==self.nmax ):
            DebugTraceMsg("time to stop commandline generator",
                          self.debug,prefix="Cmd")
            raise StopIteration
        elif len(self.list)>0:
            j = self.list[0]; self.list = self.list[1:]
            DebugTraceMsg("Popping command off list <<%s>>" % str(j),
                          self.debug,prefix="Cmd")
            self.njobs += 1; return j
        else:
            return Commandline("stall")
    def __iter__(self): return self
    def __len__(self): return len(self.list)

def testGeneratorList():
    """testGeneratorList: Generate commands from a list and count them"""
    clist = [ Commandline("foo",cores=2), Commandline("foo",cores=3), Commandline("foo") ]
    gen = CommandlineGenerator(list=clist)
    count = 0
    for g in gen:
        print g
        if count==len(clist)+1:
            assert(False)
        count += 1
    print "seen %d commands" % count
    assert(count==len(clist))

class testGeneratorStuff():
    def testGeneratorListAdd(self):
        """testGeneratorListAdd: generate commands from a list that gets expanded, use nmax"""
        clist = [ Commandline("foo",cores=2), Commandline("foo",cores=3), Commandline("foo") ]
        gen = CommandlineGenerator(list=clist,nmax=len(clist)+1)
        count = 0
        for g in gen:
            count += 1; gen.list.append(5) # this should be in an inherited class
        print "seen %d commands" % count
        assert(count==len(clist)+1)

    def testGeneratorListFinish(self):
        gen = CommandlineGenerator(list=[ 
                Commandline("foo",cores=2), Commandline("foo",cores=3), Commandline("foo") ],
                                   nmax=0)
        count = 0; nstop = 6
        for g in gen:
            count += 1; gen.list.append(3*count)
            if count==nstop: gen.abort()
        print "seen %d commands" % count
        assert(count==nstop)

    def testGeneratorStalling(self):
        gen = CommandlineGenerator(list=[],nmax=0)
        rc = gen.next(); print rc
        assert(rc["command"]=="stall")

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
            line = line.strip()
            if re.match('^ *#',line) or re.match('^ *$',line):
                continue # skip blank and comment
            if dependencies:
                split = line.split(",",2)
                if len(split)<3:
                    raise LauncherException("No task#/dependency found <<%s>>" % split)
                c,td,l = split
            else:
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

class testCommandlineGeneratorStuff():
    def testFileCommandLineGenerator(self):
        """testFileCommandLineGenerator: create a file and make sure
        we get a commandline for each file line"""
        fn = RandomFile()
        fh = open(fn,"w")
        for t in ["a","b","c","d"]:
            fh.write(t+"\n")
        fh.close()
        generator = FileCommandlineGenerator(fn)
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print r; assert(r=="a" and str(c)=="1")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print r; assert(r=="b" and str(c)=="1")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print r; assert(r=="c" and str(c)=="1")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print r; assert(r=="d" and str(c)=="1")
        try:
            rc = generator.next()
            assert(False)
        except:
            os.system("/bin/rm -f %s" % fn)
            assert(True)

    def testCoreFileCommandLineGenerator(self):
        """testCoreFileCommandLineGenerator: create a file and make sure
        we get a commandline for each file line, including core count"""
        fn = RandomFile()
        fh = open(fn,"w")
        for t in ["1,a","3,b","2,c","5,d"]:
            fh.write(t+"\n")
        fh.close()
        generator = FileCommandlineGenerator(fn,cores="file")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print "<<r=%s>>,<<c=%s>>" % (r,str(c)); assert(r=="a" and str(c)=="1")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print "<<r=%s>>,<<c=%s>>" % (r,str(c)); assert(r=="b" and str(c)=="3")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print "<<r=%s>>,<<c=%s>>" % (r,str(c)); assert(r=="c" and str(c)=="2")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print "<<r=%s>>,<<c=%s>>" % (r,str(c)); assert(r=="d" and str(c)=="5")
        try:
            rc = generator.next()
            assert(False)
        except:
            os.system("/bin/rm -f %s" % fn)
            assert(True)

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

class testDynamicGeneratorStuff():
    def testDynamicGeneratorCount(self):
        g = DynamicCommandlineGenerator()
        r = g.append( Commandline("echo foo") )
        assert(r==0)
        g = DynamicCommandlineGenerator( list=[Commandline("echo bar")] )
        r = g.append( Commandline("echo foo") )
        assert(r==1)

    def testDynamicGeneratorStalling(self):
        generator = DynamicCommandlineGenerator(list=[])
        # generator is empty
        print "len:",len(generator)
        assert(len(generator)==0)
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print r,c
        assert(r=="stall")
        #
        generator.append( Commandline("foo") )
        # generator has one item
        print "len:",len(generator)
        assert(len(generator)==1)
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print r,c
        assert(r=="foo")
        # generator is empty again
        print "len:",len(generator)
        assert(len(generator)==0)
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print r,c
        assert(r=="stall")
        generator.finish()
        # generator is empty and finished so it raises StopIteration
        try: 
            rc = generator.next()
            assert(False)
        except:
            assert(True)

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
        print "contents",dircontents
        #
        for f in dircontents:
            if re.match(self.commandfile_root,f):
                long_filename = os.path.join(self.command_directory,f)
                try: # if the file is still being written, we ignore it
                    testopen = open(long_filename,"a+")
                    testopen.close()
                except IOError:
                    print "file still open",f
                    continue
                jobnumber = f.split('-')[1]
                if jobnumber not in self.scheduled_jobs:
                    self.scheduled_jobs.append(jobnumber)
                    print "scheduling job",jobnumber
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

class testDirectoryCommandlineGenerators():
    def setup(self):
        self.dirname = MakeRandomDir()
        print "running Directory Generator in <<%s>>" % self.dirname
        self.fileroot = RandomFile()+"MECS"; self.nsleep = 5
        # create the command files
        self.nums = [ 0,2,4,6 ]
    def makefiles(self):
        for n in self.nums:
            commandfile = open( os.path.join(self.dirname,"%s-%s" % (self.fileroot,str(n))), "w")
            commandfinish = os.path.join(self.dirname,"finished-%s" % str(n))
            wait = RandomNumber(self.nsleep)
            commandfile.write("echo job %s ; sleep %d; touch %s\n" % (str(n),wait,commandfinish))
            commandfile.close()
        # create the finish file which says this is all there is
        subprocess.call(['touch', os.path.join(self.dirname,"%s-finished" % self.fileroot) ])
        self.files = [ f for f in os.listdir(self.dirname) 
                       if os.path.isfile(os.path.join(self.dirname,f)) ]
    def makejob(self,gen):
        debug="job+command+task"; workdir = NoRandomDir()
        return LauncherJob( 
            hostpool=HostPool( hostlist=HostListByName(),
                               commandexecutor=SSHExecutor(workdir=workdir,debug=debug),
                               debug=debug ),
            taskgenerator=TaskGenerator( gen,
                completion=lambda x:FileCompletion( taskid=x,
                                         stamproot="expire",stampdir=workdir),
                debug=debug )
            )
    def testDirectoryCommandlineGenerator(self):
        """testDirectoryCommandlineGenerator: test finding commands in directory"""
        self.makefiles()
        print "files:",self.files
        assert(len(self.files)==len(self.nums)+1)
        # now process the files
        gen = DirectoryCommandlineGenerator(self.dirname,self.fileroot)
        for ig,g in enumerate( gen ):
            print ig,g
        assert(ig==len(self.nums)-1)
    def testDirectoryCommandlineGeneratorJob(self):
        """testDirectoryCommandlineGeneratorJob: test finding commands in directory"""
        self.makefiles()
        print "files:",self.files
        assert(len(self.files)==len(self.nums)+1)
        # now process the files
        gen = DirectoryCommandlineGenerator(self.dirname,self.fileroot)
        j = self.makejob(gen)
        starttime = time.time()
        while True:
            r = j.tick(); print r
            if r=="finished": break
            if time.time()-starttime>self.nsleep+len(self.nums)*j.delay+1:
                print "This is taking too long"; assert(False)
        assert(True)
    def testDirectoryCommandlineGeneratorFromZero(self):
        """testDirectoryCommandlineGeneratorFromZero: start with empty directory"""
        # first we create the generator on an empty directory
        gen = DirectoryCommandlineGenerator(self.dirname,self.fileroot)
        g = gen.next()
        assert(g["command"]=="stall")
        # create the command files
        self.makefiles()
        assert(len(self.files)==len(self.nums)+1)
        # now process the files
        for ig,g in enumerate( gen ):
            print ig,g
        assert(ig==len(self.nums)-1)
    def testDirectoryCommandlineGeneratorJobFromZero(self):
        """testDirectoryCommandlineGeneratorJob: test finding commands in directory"""
        # first we create the generator on an empty directory
        gen = DirectoryCommandlineGenerator(self.dirname,self.fileroot)
        j = self.makejob(gen)
        r = j.tick(); print r
        assert(r=="stalling")
        # now actually make the files
        self.makefiles()
        print "files:",self.files
        assert(len(self.files)==len(self.nums)+1)
        # now process the files
        starttime = time.time()
        while True:
            r = j.tick(); print r
            if r=="finished": break
            if time.time()-starttime>self.nsleep+len(self.nums)*j.delay+1:
                print "This is taking too long"; assert(False)
        assert(True)

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

class TestCommandlineGenerators():
    def setup(self):
        """make a commandlines file"""
        self.fn = "unittestlines"; self.ncommand = 60
        MakeRandomCommandFile(self.fn,self.ncommand)
    def teardown(self):
        os.system("rm -f %s" % self.fn)
    def testFileCommandlineGenerator(self):
        """testFileCommandlineGenerator: exhaust the lines of a file"""
        count = 0
        for lc in FileCommandlineGenerator(self.fn,cores=1):
            print lc
            l = lc["command"]
            count += 1
        print "counted: %d, should be %d" % (count,self.ncommand)
        assert(count==self.ncommand)
    def testDynamicCommandlineGeneratorInf(self):
        """testDynamicCommandlineGeneratorInf: generate commands until dynamic finish"""
        nmax = 70
        assert(nmax>self.ncommand)
        clist = []
        with open(self.fn,"r") as coms:
            for c in coms:
                clist.append(c)
        more_commands = SleepCommandGenerator()
        generator = DynamicCommandlineGenerator( list=clist )
        for count,command in enumerate(generator):
            print count
            generator.append( Commandline(more_commands.next()) ) 
            if count==nmax:
                generator.abort()
                #generator.finish()
        assert(count==nmax)

class Completion():
    """Define a completion object for a task. 

    The base class doesn't do a lot: it immediately returns true on the 
    completion test.
    """
    workdir = "."
    def __init__(self,taskid=0):
        self.taskid = taskid
        self.stampdir = "."
    def set_workdir(self,workdir):
        self.workdir = workdir
        if self.workdir[0]!="/":
            self.workdir = os.getcwd()+"/"+self.workdir
        # create stampdir. maybe this should be in the attach method?
        if not os.path.isdir(self.workdir):
            os.makedirs(self.workdir)
    def attach(self,txt):
        """Attach a completion to a command, giving a new command"""
        return txt
    def test(self):
        """Test whether the task has completed"""
        return True

class FileCompletion(Completion):
    """FileCompletion is the most common type of completion. It appends
    to a command the creation of a zero size file with a unique name.
    The completion test then tests for the existence of that file.

    :param taskid: (keyword, required) this has to be unique. Unfortunately we can not test for that.
    :param stampdir: (keyword, optional, default is self.stampdir, which is ".") directory where the stampfile is left
    :param stamproot: (keyword, optional, default is "expire") root of the stampfile name
    """
    stamproot = "expire"
    stampdir = "."
    def __init__(self,**kwargs):
        taskid = kwargs.pop("taskid",-1)
        if taskid==-1:
            raise LauncherException("Need an explicit task ID")
        Completion.__init__(self,taskid)
        self.set_workdir( kwargs.pop("stampdir",self.stampdir) )
        self.stamproot = kwargs.pop("stamproot",self.stamproot)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed FileCompletion args: %s" % str(kwargs))
    def stampname(self):
        """Internal function that gives the name of the stamp file,
        including directory path"""
        return "%s/%s%s" % (self.workdir,self.stamproot,str(self.taskid))
    def attach(self,txt):
        """Append a 'touch' command to the txt argument"""
        os.system("mkdir -p %s" % self.workdir)
        if re.match('^[ \t]*$',txt):
            return "touch %s" % self.stampname()
        else:
            return "%s ; touch %s" % (txt,self.stampname())
    def test(self):
        """Test for the existence of the stamp file"""
        return os.path.isfile(self.stampname())
    def cleanup(self):
        os.system("rm -f %s" % self.stampname())

class Task():
    """A Task is an abstract object associated with a commandline

    :param command: (required) Commandline object; note that this contains the core count
    :param completion: (keyword, optional) Completion object; if unspecified the trivial completion is used.
    :param taskid: (keyword) identifying number of this task; has to be unique in a job, also has to be equal to the taskid of the completion
    :param debug: (keyword, optional) string of debug keywords
    """
    def __init__(self,command,**kwargs):
        self.command = command["command"]
        # make a default completion if needed
        self.completion = kwargs.pop("completion",None)
        self.taskid = kwargs.pop("taskid",0)
        if self.completion is None:
            self.completion = Completion(taskid=self.taskid)
        if self.taskid!=self.completion.taskid:
            raise LauncherException("Incompatible taskids")
        self.size = command["cores"]
        self.debugs = kwargs.pop("debug","")
        self.debug = re.search("task",self.debugs)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed args: %s" % str(kwargs))
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
        self.pool = kwargs.pop("pool",None)
        self.starttick = kwargs.pop("starttick",0)
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
        DebugTraceMsg(
            "starting task %d of size %d on <<%s>>\nin cwd=<<%s>>\ncmd=<<%s>>" % \
                (self.taskid,self.size,str(self.pool),os.getcwd(),wrapped),
            self.debug,prefix="Task")
        self.starttime = time.time()
        commandexecutor = self.pool.pool.commandexecutor
        commandexecutor.execute(wrapped,pool=self.pool)
        self.has_started = True
        DebugTraceMsg("started %d" % self.taskid,self.debug,prefix="Task")
    def line_with_completion(self):
        """Return the task's commandline with completion attached"""
        line = re.sub("PYL_ID",str(self.taskid),self.command)
        return self.completion.attach(line)
    def isRunning(self):
        return self.has_started
    def hasCompleted(self):
        """Execute the completion test of this Task"""
        completed = self.has_started and self.completion.test()
        if completed:
            self.runningtime = time.time()-self.starttime
            DebugTraceMsg("completed %d in %5.3f" % (self.taskid,self.runningtime),
                          self.debug,prefix="Task")
        return completed
    def __repr__(self):
        s = "Task %d, commandline: [%s], pool size %d" \
            % (self.taskid,self.command,self.size)
        return s

class testCompletions():
    def setup(self):
        # get rid of old workdirs
        tmpdir = os.getcwd()+"/"+Executor.default_workdir
        if os.path.isdir(tmpdir):
            try:
                shutil.rmtree(tmpdir)
            except:
                os.system("ls -l %s" % tmpdir)
                os.system("rm -f %s/*" % tmpdir)
    def teardown(self):
        self.setup()
    def testTrivialCompletion(self):
        task = Task( Commandline("/bin/true") )
        assert(not task.hasCompleted())
        task.start_on_nodes()
        assert(task.hasCompleted())
    def testCurDirCompletion(self):
        os.system("rm -f expirefoo5")
        task = Task( Commandline("/bin/true"),taskid=5,
              completion=FileCompletion(taskid=5,stamproot="expirefoo",stampdir=".",))
        print "expected stamp:",task.completion.stampname()
        task.start_on_nodes()
        time.sleep(1)
        assert(os.path.isfile("./expirefoo5"))
        os.system("rm -f expirefoo5")
    def testSubDirCompletion(self):
        os.system("rm -rf launchtest")
        task = Task( Commandline("/bin/true"),taskid=7,
            completion=FileCompletion(taskid=7,
                                 stamproot="expirefoo",stampdir="launchtest",))
        task.start_on_nodes()
        time.sleep(1)
        assert(os.path.isfile("launchtest/expirefoo7"))
        os.system("rm -rf launchtest")

class RandomSleepTask(Task):
    """Make a task that sleeps for a random amount of time.
    This is for use in many many unit tests.

    :param taskid: unique identifier (keyword, required)
    :param t: maximum running time (keyword, optional; default=10)
    :param tmin: minimum running time (keyword, optional; default=1)
    :param completion: Completion object (keyword, optional; if you leave this unspecified, the next two parameters become relevant
    :param stampdir: name of the directory where to leave the stamp file (optional, default=current dir)
    :param stamproot: filename stemp for the stamp file (optional, default="sleepexpire")
    """
    stampdir = "."
    stamproot = "sleepexpire"
    def __init__(self,**kwargs):
        taskid = kwargs.pop("taskid",-1)
        if taskid==-1:
            raise LauncherException("Need an explicit sleep task ID")
        t = kwargs.pop("t",10); tmin = kwargs.pop("tmin",1);
        stamproot = kwargs.pop("stamproot",RandomSleepTask.stamproot)
        stampdir = kwargs.pop("stampdir",RandomSleepTask.stampdir)
        completion = kwargs.pop("completion",None)
        if completion is None:
            completion = FileCompletion\
                (taskid=taskid,stamproot=stamproot,stampdir=stampdir)
        command = SleepCommandGenerator(nmax=1,tmax=t,tmin=tmin).next()
        Task.__init__(self,Commandline(command),taskid=taskid,completion=completion,**kwargs)
        
class testTasksOnSingleNode():
    stampname = "pylauncher_tmp_singlenode_tasktest"
    def setup(self):
        os.system( "rm -f %s*" % RandomSleepTask.stamproot )
        tmpdir = os.getcwd()+"/"+Executor.default_workdir
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir)
        self.pool = LocalHostPool(nhosts=1)#OneNodePool( Node(HostName()) )
    def testLeaveStampOnOneNode(self):
        """testLeaveStampOnOneNode: leave a stamp on a one-node pool"""
        nsleep = 5
        start = time.time()
        t = RandomSleepTask(taskid=1,t=nsleep,
                            completion=FileCompletion(taskid=1,
                                                      stamproot=self.stampname),
                            debug="exec+task+ssh")
        print "starting task:",t
        t.start_on_nodes(pool=self.pool.request_nodes(1))
        assert(time.time()-start<1)
        time.sleep(nsleep+1)
        dircontent = os.listdir(t.completion.stampdir)
        print "looking for stamp <<%s>> in <<%s>>" % \
            (self.stampname,t.completion.stampdir)
        print sorted(dircontent)
        stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
        print "stamps:",stamps
        assert(len(stamps)==1)

class testTasks():
    stampname = "pylauncher_tmp_tasktest"
    def setup(self):
        # stamp dir
        self.stampdir = MakeRandomDir() # os.getcwd()+"/"+RandomDir()+"_tasktestdir"
        # if os.path.isdir(self.stampdir):
        #     shutil.rmtree(self.stampdir)
        # os.mkdir(self.stampdir)
        # tmp dir
        self.tmpdir = MakeRandomDir() # os.getcwd()+"/"+RandomDir()+"_workdir"
        # if os.path.isdir(self.tmpdir):
        #     shutil.rmtree(self.tmpdir)
        # os.mkdir(self.tmpdir)
        #
        os.system( "rm -f %s*" % FileCompletion.stamproot )
        os.system( "rm -f %s*" % RandomSleepTask.stamproot )
        self.workdir = MakeRandomDir()
        self.ntasks = 10
        self.pool = LocalHostPool(nhosts=self.ntasks,workdir=self.workdir) # os.getcwd()+"/"+RandomDir())
    def testImmediateIssue(self):
        """testImmediateIssue: make sure tasks are run in the background"""
        import time
        start = time.time()
        for i in range(self.ntasks):
            t = RandomSleepTask(taskid=i,t=6,stamproot=self.stampname)
            t.start_on_nodes(pool=self.pool.request_nodes(1))
        assert(time.time()-start<1)
    def testLeaveStamp(self):
        """testLeaveStamp: make sure tasks leave a stampfile"""
        nsleep = 5
        start = time.time()
        for i in range(self.ntasks):
            t = RandomSleepTask(taskid=i,t=nsleep,
                                completion=FileCompletion(taskid=i,
                                                          stamproot=self.stampname))
            t.start_on_nodes(pool=self.pool.request_nodes(1))
            stampdir = t.completion.stampdir
        assert(time.time()-start<1)
        time.sleep(nsleep+1)
        dircontent = os.listdir(stampdir)
        stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
        print "stamps:",stamps
        assert(len(stamps)==self.ntasks)
    def testCompleteOnStamp(self):
        """testCompleteOnStamp: make sure stampfiles are detected"""
        stamproot = "expiresomething"
        nsleep = 5; tasks = []
        start = time.time()
        for i in range(self.ntasks):
            t = RandomSleepTask(taskid=i,t=nsleep,
                                completion=FileCompletion(stamproot=stamproot,taskid=i))
            t.start_on_nodes(pool=self.pool.request_nodes(1))
            tasks.append(t)
        finished = [ False for i in range(self.ntasks) ]
        while True:
            if reduce( lambda x,y: x and y,
                       [ t.hasCompleted() for t in tasks ] ): break
            if time.time()-start>nsleep+2:
                print "this is taking too long"
                assert(False)
        dircontent = os.listdir(".")
        print "dir content:",sorted(dircontent)
        stamps = [ f for f in dircontent if re.search(stamproot,f) ]
        print "stamps:",stamps
        assert(len(stamps)==self.ntasks)
    def testCompleteOnDefaultStamp(self):
        """testCompleteOnDefaultStamp: make sure stampfiles are detected in default setup"""
        tasks = []; nsleep = 5
        start = time.time()
        for i in range(self.ntasks):
            t = RandomSleepTask(taskid=i,t=nsleep,
                       completion=FileCompletion(stampdir=self.stampdir,taskid=i))
            t.start_on_nodes(pool=self.pool.request_nodes(1))
            tasks.append(t)
        stamproot = t.completion.stamproot
        print "stamps based on:",stamproot
        finished = [ False for i in range(self.ntasks) ]
        while True:
            print "tick"
            if reduce( lambda x,y: x and y,
                       [ t.hasCompleted() for t in tasks ] ): break
            if time.time()-start>nsleep+3:
                print "this is taking too long"
                assert(False)
            time.sleep(1)
        dircontent = os.listdir(self.stampdir)
        stamps = [ f for f in dircontent if re.match("%s" % stamproot,f) ]
        print "stamps:",sorted(stamps)
        assert(len(stamps)==self.ntasks)

#
# different ways of starting up a job
def launcherqsubber(task,line,hosts,poolsize):
    command = "qsub %s" % line
    return command

class Node():
    """A abstract object for a slot to execute a job. Most of the time
    this will correspond to a core.

    A node can have a task associated with it or be free."""
    def __init__(self,host=None,core=None,nodeid=-1):
        self.hostname = host; self.core = core
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
        return "h:%s, c:%s, id:%s" % (self.hostname,str(self.core),str(self.nodeid))

def testNode():
    assert(True)
    return
    nn = 5
    for i in range(nn):
        n = Node()
    assert(n.nodeid==nn-1)
    Node.i = 0
    nn = 2
    for i in range(nn):
        n = Node()
    assert(n.nodeid==nn-1)

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
        #print "set HostPoolBase commandexecutor to",str(self.commandexecutor)
        workdir = kwargs.pop("workdir",None)
        if self.commandexecutor is None:
            self.commandexecutor = LocalExecutor(workdir=workdir)
        elif workdir is not None:
            raise LauncherException("workdir arg is ignored with explicit executor")
        self.debugs = kwargs.pop("debug","")
        self.debug = re.search("host",self.debugs)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed HostPool args: %s" % str(kwargs))
    def append_node(self,host="localhost",core=0):
        """Create a new item in this pool by specifying either a Node object
        or a hostname plus core number. This function is called in a loop when a
        ``HostPool`` is created from a ``HostList`` object."""
        if isinstance(host,(Node)):
            node = host
        else:
            node = Node(host,core,nodeid=len(self.nodes))
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
        if workdir is None:
            executor = LocalExecutor()
        else:
            executor = LocalExecutor(workdir=workdir)
        HostPoolBase.__init__\
            (self,commandexecutor=kwargs.pop("commandexecutor",executor),
             debug=kwargs.pop("debug",""))
        hostlist = kwargs.pop("hostlist",None)
        if hostlist is not None and not isinstance(hostlist,(HostList)):
            raise LauncherException("hostlist argument needs to be derived from HostList")
        nhosts = kwargs.pop("nhosts",None)
        if hostlist is not None:
            nhosts = len(hostlist)
            for h in hostlist:
                self.append_node(host=h['host'],core = h['core'])
        elif nhosts is not None:
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

def testHostPoolN():
    # get rid of old workdirs
    tmpdir = os.getcwd()+"/"+Executor.default_workdir
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)
    # test
    p = HostPool(nhosts=5)
    # request a 3 node pool
    pool = p.hosts([1,3])
    assert(len(pool)==2)
    assert(pool[0].nodeid==1 and pool[1].nodeid==3)
    p1 = p.request_nodes(3)
    assert(len(p1)==3)
    task = 27
    p.occupyNodes(p1,task)
    # it is not possible to get 4 more nodes
    p2 = p.request_nodes(4)
    assert(p2 is None)
    # see if the status is correctly rendered
    assert(not p[0].free and p[3].free)
    assert(p[0].nodestring()==str(task) and p[3].nodestring()=="X")
    # after we release used pool, we can request more
    p.releaseNodesByTask(task)
    p2 = p.request_nodes(4)
    assert(len(p2)==4)
    # cleanup
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)
    
def testStartTaskOnPool():
    import random
    # get rid of old workdirs
    tmpdir = os.getcwd()+"/"+Executor.default_workdir
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)
    # test
    fn = "pwd.utest"; word = str(random.random())
    os.system("/bin/rm -f %s" % fn)
    task = Task( Commandline("echo %s > %s" % (word,fn)) )
    task.start_on_nodes(pool=LocalHostPool(nhosts=1).request_nodes(1))
    time.sleep(1)
    with open(fn,"r") as f:
        for l in f:
            l = l.strip(); print l
            assert(l==word)
    os.system("/bin/rm -f %s" % fn)
    assert(True)
    # cleanup
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)

class HostList():
    """Object describing a list of hosts. Each host is a dictionary
    with a ``host`` and ``core`` field.

    Arguments:

    * list : list of hostname strings
    * tag : something like ``.tacc.utexas.edu`` may be necessary to ssh to hosts in the list

    This is an iteratable object; it yields the host/core dictionary objects.
    """
    def __init__(self,hostlist=[],tag=""):
        self.hostlist = []; self.tag = tag; self.uniquehosts = []
        for h in hostlist:
            self.append(h)
    def append(self,h,c=0):
        """
        Arguments:

        * h : hostname
        * c (optional, default zero) : core number
        """
        if not re.search(self.tag,h):
            h = h+self.tag
        if h not in self.uniquehosts:
            self.uniquehosts.append(h)
        self.hostlist.append( {'host':h, 'core':c} )
    def __len__(self):
        return len(self.hostlist)
    def __iter__(self):
        for h in self.hostlist:
            yield h

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
        n=N/p
        hlist = hs.expand_hostlist(hlist_str)
        for h in hlist:
            for i in range(int(n)):
                self.append(h,i)

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
    # Non-TACC example, this is for Georgia Institute of Technology's PACE
    if "pace" in namesplit:
        return namesplit[1]
    # case: unknown
    return None

def ClusterHasSharedFileSystem():
    """This test is only used in some unit tests"""
    return ClusterName() in ["ls4","ls5","maverick","stampede","stampede2","mic","frontera"]

def JobId():
    """This function is installation dependent: it inspects the environment variable
    that holds the job ID, based on the actual name of the host (see
     ``HostName``): this should only return a number if we are actually in a job.
    """
    hostname = ClusterName()
    if hostname=="ls4":
        return os.environ["JOB_ID"]
    elif hostname in ["ls5","maverick","stampede","stampede2","frontera"]:
        return os.environ["SLURM_JOB_ID"]
    elif hostname in ["pace"]:
        return os.environ["PBS_JOBID"]
    else:
        return None

def HostListByName(**kwargs):
    """Give a proper hostlist. Currently this work for the following TACC hosts:

    * ``ls4``: Lonestar4, using SGE
    * ``ls5``: Lonestar5, using SLURM
    * ``maverick``: Maverick, using SLURM
    * ``stampede``: Stampede, using SLURM
    * ``mic``: Intel Xeon PHI co-processor attached to a compute node

    We return a trivial hostlist otherwise.
    """
    cluster = ClusterName()
    if cluster=="ls4":
        return SGEHostList(tag=".ls4.tacc.utexas.edu",**kwargs)
    elif cluster=="ls5": # ls5 nodes don't have fully qualified hostname
        return SLURMHostList(tag="",**kwargs)
    elif cluster=="maverick":
        return SLURMHostList(tag=".maverick.tacc.utexas.edu",**kwargs)
    elif cluster=="stampede":
        return SLURMHostList(tag=".stampede.tacc.utexas.edu",**kwargs)
    elif cluster in ["stampede2","stampede2-skx"]:
        return SLURMHostList(tag=".stampede2.tacc.utexas.edu",**kwargs)
    elif cluster in ["frontera"]:
        return SLURMHostList(tag=".frontera.tacc.utexas.edu",**kwargs)
    elif cluster  in ["pace"]:
        return PBSHostList(**kwargs)
    elif cluster=="mic":
        return HostList( ["localhost" for i in range(60)] )
    else:
        return HostList(hostlist=[HostName()])
        
def testTACChostlist():
    for h in HostListByName():
        print "hostfile line:",h
        assert( 'core' in h and 'host' in h )
        host = h["host"].split(".")
        #assert( len(host)>1 and host[1]==HostName() )

class DefaultHostPool(HostPool):
    """A HostPool object based on the hosts obtained from the
    ``HostListByName`` function, and using the ``SSHExecutor`` function.
    """
    def __init__(self,**kwargs):
        debugs = kwargs.pop("debug","")
        hostlist = kwargs.pop("hostlist",HostListByName())
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

def testPEhostpools():
    """testPEhostpools: Test that we get the right number of cores on the TACC hosts"""
    # get rid of old workdirs
    tmpdir = os.getcwd()+"/"+Executor.default_workdir
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)
    # test
    cluster = ClusterName()
    pool = DefaultHostPool()
    if cluster=="ls5":
        assert(len(pool)%24==0)
    elif cluster=="maverick":
        assert(len(pool)%20==0)
    elif cluster=="stampede":
        assert(len(pool)%16==0)
    elif cluster=="stampede2":
        assert(len(pool)>0)
    elif cluster=="frontera":
        assert(len(pool)>0)
    elif cluster=="ls4":
        assert(len(pool)%12==0)
    else:
        print "Detecting host",cluster
        assert(True)
    # cleanup
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)

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

def testHostPoolWorkdirforcing():
    os.system("/bin/rm -rf "+Executor.default_workdir)
    os.mkdir(Executor.default_workdir)
    try:
        exc = Executor()
        assert(False)
    except:
        assert(True)
    exc = Executor(force_workdir=True)
    assert(True)

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
        self.debug = kwargs.pop("debug",False)
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
            if locator is None:
                DebugTraceMsg("could not find nodes for <%s>" % str(t),
                              self.debug,prefix="Queue")
                max_gap = requested_gap-1
                continue
            if self.submitdelay>0:
                time.sleep(self.submitdelay)
            DebugTraceMsg("starting task <%s> on locator <%s>" % (str(t),str(locator)),
                          self.debug,prefix="Queue")
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
        return "completed: "+str( CompactIntList(completed) )+\
               "\naborted: " +str( CompactIntList(aborted) )+\
               "\nqueued: " +str( CompactIntList(queued) )+\
               "\nrunning: "+str( CompactIntList(running) )+"."
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
        f = open("queuestate","w")
        f.write("queued\n")
        for t in self.queue:     f.write("%s: %s\n" % (t.taskid,t.command))
        f.write("running\n")
        for t in self.running:   f.write("%s: %s\n" % (t.taskid,t.command))
        f.write("completed\n")
        for t in self.completed: f.write("%s: %s\n" % (t.taskid,t.command))
        f.close()
    def final_report(self):
        """Return a string describing the max and average runtime for each task."""
        times = [ t.runningtime for t in self.completed]
        message = """# tasks completed: %d
tasks aborted: %d
max runningtime: %6.2f
avg runningtime: %6.2f
""" % ( len(self.completed), len(self.aborted),
        max( times ), sum( times )/len(self.completed) )
        return message

def testTaskQueue():
    """testTaskQueue: queue and detect a task in a queue
    using the default task prefixer and completion tester"""
    # get rid of old workdirs
    tmpdir = os.getcwd()+"/"+Executor.default_workdir
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)
    # test
    pool = HostPool(nhosts=5)
    queue = TaskQueue()
    nsleep = 5; t_id = 13
    task = RandomSleepTask(taskid=t_id,t=nsleep)
    queue.enqueue(task)
    queue.startQueued(pool)
    assert(task in queue.running)
    time.sleep(nsleep)
    complete_id = queue.find_recently_completed().taskid
    print "found completed:",complete_id
    assert(complete_id==t_id)
    task.completion.cleanup()
    assert(True)
    # cleanup
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)

def testTaskQueueWithLauncherdir():
    """testTaskQueueWithLauncherdir: same, but test correct use of launcherdir"""
    # get rid of old workdirs
    tmpdir = os.getcwd()+"/"+Executor.default_workdir
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)
    # test
    pool = HostPool(nhosts=5)
    dirname = "noselaunch"
    os.system("rm -rf %s" % dirname)
    queue = TaskQueue()
    nsleep = 3; t_id = 14
    task = RandomSleepTask(taskid=t_id,t=nsleep,
                           completion=FileCompletion(stampdir=dirname,taskid=t_id))
    queue.enqueue(task)
    queue.startQueued(pool)
    assert(task in queue.running)
    time.sleep(nsleep)
    complete_id = queue.find_recently_completed().taskid
    print "completed:",complete_id
    assert(complete_id==t_id)
    files = os.listdir(dirname)#queue.launcherdir)
    print files
    assert(len(files)==1)
    os.system("/bin/rm -rf %s" % dirname)
    assert(True)
    # cleanup
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)

class TaskGenerator():
    """iterator class that can yield the following:

    * a Task instance, or 
    * the keyword ``stall``; this indicates that the commandline generator is stalling and this will be resolved when the outer environment does an ``append`` on the commandline generator.
    * the ``pylauncherBarrierString``; in this case the outer environment should not call the generator until all currently running tasks have concluded.
    * the keyword ``stop``; this means that the commandline generator is exhausted. The ``next`` function can be called repeatedly on a stopped generator.

    You can iterate over an instance, or call the ``next`` method. The ``next`` method
    can accept an imposed taskcount number.

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
        self.taskcount = 0; self.paused = False
        self.debugs = kwargs.pop("debug","")
        self.debug = re.search("task",self.debugs)
        self.completion = kwargs.pop("completion",lambda x:Completion(taskid=x))
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
                return Task(comm,taskid=taskid,debug=self.debugs,
                            completion=self.completion(taskid),
                            )
    def __iter__(self): return self

def TaskGeneratorIterate( gen ):
    """In case you want to iterate over a TaskGenerator, use this generator routine"""
    while True:
        t = gen.next()
        if t=="stop":
            raise StopIteration
        yield t

class TestTaskGenerators():
    def countedcommand(self):
        count = self.icommand; self.icommand += 1
        return "/bin/true command%d" % count
    def setup(self):
        """make a commandlines file"""
        self.fn = "unittestlines"; self.dir = "tmp_dir"; self.ncommand = 60
        self.icommand = 0
        commandlines = open(self.fn,"w")
        for i in range(self.ncommand):
            if i%5==0:
                commandlines.write("# arbitrary comment\n")
            if i%7==0:
                commandlines.write("\n")
            commandlines.write(self.countedcommand()+"\n")
        commandlines.close()
    def teardown(self):
        os.system("rm -rf %s %s" % (self.fn,self.dir))
    def testFileTaskGenerator(self):
        """testFileTaskGenerator: test that the taskgenerator can deal with a file"""
        count = 0
        g = TaskGenerator( FileCommandlineGenerator(self.fn,cores=1,debug="command"),
                           debug="task")
        while True:
            try:
                t  = g.next()
            except: break
            count += 1
        print "%d s/b %d" % (count,self.ncommand)
        assert(count==self.ncommand)
    def testFileTaskGeneratorIteratable(self):
        """testFileTaskGeneratorIteratable: test that the taskgenerator can deal with a file"""
        count = 0
        for t in TaskGeneratorIterate( TaskGenerator( 
                FileCommandlineGenerator(self.fn,cores=1,debug="command"),
                debug="task") ):
            count += 1
        print "%d s/b %d" % (count,self.ncommand)
        assert(count==self.ncommand)
    def testFileTaskGeneratorNext(self):
        """testFileTaskGeneratorNext: file task generator, but using a while/next loop"""
        count = 0; generator = TaskGenerator( 
            FileCommandlineGenerator(self.fn,cores=1,debug="command"),
            debug="task")
        starttime = time.time()
        while True:
            try:
                t = generator.next()
            except: break
            count += 1
            if time.time()-starttime>3:
                print "this is taking too long"
                assert(False)
        print "%d s/b %d" % (count,self.ncommand)
        assert(count==self.ncommand)
    def testDynamicTaskGeneratorLong(self):
        """testDynamicTaskGeneratorLong: generate tasks until dynamic finish"""
        nmax = self.ncommand+10
        generator = TaskGenerator( DynamicCommandlineGenerator(debug="command") )
        count = 0
        while True:
            if count>=nmax:
                generator.commandlinegenerator.finish()
            else:
                generator.commandlinegenerator.append( Commandline( self.countedcommand()) )
            try:
                t = generator.next()
            except:
                break
            count += 1
        print "count %d s/b %d" % (count,nmax)
        assert(count==nmax)
    def testDynamicTaskGeneratorShort(self):
        """testDynamicTaskGeneratorShort: generate tasks until dynamic finish"""
        nmax = self.ncommand-10
        generator = TaskGenerator( DynamicCommandlineGenerator(debug="command") )
        count = 0
        while True:
            if count==nmax:
                generator.commandlinegenerator.finish()
            else:
                generator.commandlinegenerator.append( Commandline( self.countedcommand()) )
            try:
                t = generator.next()
            except:
                break
            count += 1
        print "count %d s/b %d" % (count,nmax)
        assert(count==nmax)
    def ttestTaskGeneratorTmpDir(self):
        nmax = self.ncommand; pool = HostPool(nhosts=nmax)
        count = 0
        for t in TaskGeneratorIterate( TaskGenerator( FileCommandlineGenerator(self.fn,cores=1),
              completion=lambda x:FileCompletion(taskid=x,stampdir=self.dir) ) ):
            locator = pool.request_nodes(1)
            if locator is None:
                raise LauncherException("there should be space")
            t.start_on_nodes(locator)
        files = os.listdir(self.dir); print files
        assert(len(files)==nmax)
    def testFileTaskGeneratorSkip(self):
        """testFileTaskGeneratorSkip: test that the taskgenerator can skip"""
        count = 0; skip = [2,4,5,6,7,8,11,13]
        assert(skip[-1]<self.ncommand)
        g = TaskGenerator( FileCommandlineGenerator(self.fn,cores=1,debug="command"),
                           skip=skip, debug="task")
        while True:
            try:
                t  = g.next()
            except: break
            count += 1
        print "executed %d plus skipped %d s/b %d" % (count,len(skip),self.ncommand)
        assert(count+len(skip)==self.ncommand)

def testModuleCommandline():
    ntasks = 40; fn = "modtest"
    MakeRandomSleepFile(fn,ntasks)
    os.system("/bin/rm -f %s" % fn)
    assert(True)


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
    :param workdir: (optional, default="pylauncher_tmpdir_exec") directory for exec and out files
    :param debug: (optional) string of debug modes; include "exec" to trace this class

    Important note: the ``workdir`` should not already exist. You have to remove it yourself.
    """
    default_workdir = "pylauncher_tmpdir_exec"
    execstring = "exec"
    outstring = "out"
    def __init__(self,**kwargs):
        self.catch_output = kwargs.pop("catch_output",True)
        if self.catch_output:
            self.append_output = kwargs.pop("append_output",None)
        self.debugs = kwargs.pop("debug","")
        self.debug = re.search("exec",self.debugs)
        self.count = 0
        workdir = kwargs.pop("workdir",None)
        if workdir is None:
            self.workdir = self.default_workdir
        else: self.workdir = workdir
        force_workdir = kwargs.pop("force_workdir",False)
        if self.workdir[0]!="/":
            self.workdir = os.getcwd()+"/"+self.workdir
        DebugTraceMsg("Using executor workdir <<%s>>" % self.workdir,
                     self.debug,prefix="Exec")
        if os.path.isfile(self.workdir):
            raise LauncherException(
                "Serious problem creating executor workdir <<%s>>" % self.workdir)
        elif not os.path.isdir(self.workdir):
            os.mkdir(self.workdir)
            # if force_workdir:
            #     os.system("/bin/rm -rf %s" % self.workdir)
            # else:
            #     raise LauncherException(
            #         "I will not reuse an executor workdir <<%s>>" % self.workdir)
        if not self.workdir_is_safe():
            raise LauncherException("Unsafe working dir <<%s>>; pls remove" % self.workdir)
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
    def wrap(self,command):
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
                #execoutname = self.append_output
            else: 
                pipe = ">"
                #execoutname =  "%s/%s%d" % (self.workdir,self.outstring,self.count)
            wrappedcommand = "%s %s %s 2>&1" % (execfilename,pipe,execoutname)
        else:
            wrappedcommand = execfilename
        DebugTraceMsg("file <<%s>>\ncontains <<%s>>\nnew commandline <<%s>>" % \
                          (execfilename,command,wrappedcommand),
                      self.debug,prefix="Exec")
        return wrappedcommand
    def execute(self,command,**kwargs):
        raise LauncherException("Should not call default execute")
    def terminate(self):
        return

def testExecutorTmpDir():
    # cleanup from failed tests
    tmpdir = os.getcwd()+"/abc"
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)
    # test
    here = os.getcwd()
    assert( Executor(workdir="abc").workdir_is_safe() )
    there = os.getcwd()
    assert(here==there)
    # cleanup
    tmpdir = os.getcwd()+"/abc"
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)

def testExecutorTmpDirRandom():
    wd = "a%d" % RandomID(); print "testing with executor tmpdir",wd
    # cleanup from failed tests
    tmpdir = os.getcwd()+"/"+wd
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)
    # test
    x = Executor(workdir=wd)
    assert( os.path.isdir(os.getcwd()+"/"+wd) )
    x.cleanup()
    assert( not os.path.isdir(os.getcwd()+"/"+wd) )
    try:
        Executor(workdir=".")
        assert(False)
    except: assert(True)
    try:
        Executor(workdir="..")
        assert(False)
    except: assert(True)
    try:
        Executor(workdir="../foo")
        assert(False)
    except: assert(True)
    # cleanup from failed tests
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)

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

def testLocalExecutor():
    """testLocalExecutor: check that local execution works"""
    wd = NoRandomDir()
    x = LocalExecutor(debug="exec",workdir=wd)
    touched = RandomFile()
    # test the basic mechanisms
    x.execute("touch %s" % touched)
    print os.listdir(x.workdir)
    assert(os.path.isdir(wd))
    assert(os.path.isfile(wd+"/exec0"))
    time.sleep(1)
    assert(os.path.isfile(wd+"/out0"))
    assert(os.path.isfile(touched))
    # test proper delays
    touched = RandomFile()
    x.execute("%s; touch %s" % (SingleSleepCommand(3,tmin=3),touched))
    time.sleep(1)
    assert(not os.path.isfile(touched))
    time.sleep(3)
    assert(os.path.isfile(touched))
    x.cleanup()
    os.system("/bin/rm -f %s" % touched)
    assert( not os.path.isdir(wd))

def testLocalHostPool():
    tmpdir = os.getcwd()+"/"+Executor.default_workdir
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)
    pool = LocalHostPool(nhosts=2,debug="host+exec")
    tval = 3
    t1 = RandomSleepTask(taskid=1,t=tval,tmin=tval)
    t2 = RandomSleepTask(taskid=2,t=tval,tmin=tval)
    start = time.time()
    loc1 = pool.request_nodes(1)
    assert(loc1 is not None)
    t1.start_on_nodes(pool=loc1)
    pool.occupyNodes(loc1,1)
    loc2 = pool.request_nodes(1)
    assert(loc2 is not None)
    t1.start_on_nodes(pool=loc2)
    pool.occupyNodes(loc2,2)
    pool.releaseNodesByTask(1)
    pool.releaseNodesByTask(2)
    loc = pool.request_nodes(2)
    assert(loc is not None)

def ssh_client(host,debug=False):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if debug:
        print "Create paramiko ssh client to",host
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
        DebugTraceMsg("Set up connection to <<%s>>" % host,self.debug,prefix="SSH")
        if False and host in self.node_client_dict:
            node.ssh_client = self.node_client_dict[host]
            node.ssh_client_unique = False
        else:
            print "making ssh client to host",host
            node.ssh_client = ssh_client(host,debug=self.debug)
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
        if len(kwargs)>0:
            raise LauncherException("Unprocessed SSHExecutor args: %s" % str(kwargs))
        # construct the command line with environment, workdir and expiration
        env_line = environment_list()
        wrapped_line = self.wrap(env_line+usercommand+"\n")
        DebugTraceMsg("Executing << ( %s ) & >> on <<%s>>" % (wrapped_line,hostname),
                      self.debug,prefix="SSH")
        ssh = self.node_client_dict[hostname]
        try:
            stdin,stdout,stderr = ssh.exec_command("( %s ) &" % wrapped_line)
#             transport = ssh.get_transport()
#             self.session = transport.open_session()
#             self.session.setblocking(0) # Set to non-blocking mode
#             self.session.get_pty()
#             self.session.invoke_shell()
#             # Send command
#             self.session.send('watch -n1 ps\n')
        except : # old paramiko value? ChannelException:
            DebugTraceMsg("Channel exception; let's see if this blows over",prefix="SSH")
            time.sleep(3)
            ssh.exec_command("( %s ) &" % wrapped_line)
    def end_execution(self):
        self.session.send('\x03')
        self.session.close()

class testPermanentSSHconnection():
    def setup(self):
        self.stampname = "prefixtasktest"
        command = "rm -f %s*" % self.stampname
        os.system(command)
        command = "rm -f %s*" % FileCompletion.stamproot
        os.system(command)
        command = "rm -f %s*" % RandomSleepTask.stamproot
        os.system(command)
        tmpdir = os.getcwd()+"/"+Executor.default_workdir
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir)
    def teardown(self):
        self.setup()
    def testRemoteSSH(self):
        """testRemoteSSH: This tests whether we we ssh to the right host.
        Create a task that pipes the output of `hostname' to a file,
        then read that file (using shared file system if present) 
        and compare the contents to where we ssh'ed."""
        hosts = DefaultHostPool().unique_hostnames()
        if len(hosts)>1:
            print "available hosts:",hosts
            self.setup()
            pool = HostPool(hostlist=HostList([hosts[1]]),
                            commandexecutor=SSHExecutor(debug="exec"))
            fn = "testremotessh"; fn = os.getcwd()+"/"+fn
            t = Task( Commandline("hostname > %s; sleep 1" % fn) )
            t.start_on_nodes(pool=HostLocator(pool=pool,extent=1,offset=0))
            time.sleep(1)
            if ClusterHasSharedFileSystem():
                try:
                    with open(fn) as outfile:
                        for line in outfile:
                            line = line.strip(); print "<<%s>> <<%s>>" % (line,hosts[1])
                            assert(line==hosts[1])
                            break
                except: 
                    assert(False)
            else:
                command = "cat %s/%s" % (pwd,fn)
                p = subprocess.Popen(command,shell=True,stdout=subprocess.PIPE)
                hostread = p.communicate()[0].strip(); print hostread
                assert(hostread==hosts[1])
            os.system("/bin/rm -f %s" % fn)
        else: assert(True)
    def testSSHImmediateIssue(self):
        """testSSHImmediateIssue: make sure ssh tasks are run in the background"""
        t = RandomSleepTask(taskid=1,t=6,stamproot=self.stampname)
        pool = DefaultHostPool()
        start = time.time()
        t.start_on_nodes(pool=HostLocator(pool=pool,extent=1,offset=0))
        elapsed = time.time()-start
        print "elapsed time for an ssh",elapsed
        assert(elapsed<1)
    def ttestSSHbusy(self):
        """testSSHbusy: start a couple of sleep tasks and confirm their existence.
        This uses a local ps through subprocess.
        """
        n = 3; t = 4
        pool = DefaultHostPool(debug="host+exec+ssh")
        tasks = [ RandomSleepTask(taskid=i,t=t,tmin=t,debug="task+exec") 
                  for i in range(n) ]
        sshstart = time.time()
        for i,task in enumerate(tasks):
            task.start_on_nodes( pool=HostLocator(pool=pool,extent=1,offset=i) )
            assert( not task.hasCompleted() )
        assert(time.time()-sshstart<1)
        assert(t>=3)
        for task in tasks:
            assert( not task.hasCompleted() )
            assert( task.isRunning() )
        ps_command = "ps guwax | grep exec[0-9]"
        p = subprocess.Popen(ps_command,shell=True,stdout=subprocess.PIPE)
        psread = p.communicate()[0].strip().split("\n") # stdout, strip \n, split
        time.sleep(t+1)
        for task in tasks:
            assert( task.hasCompleted() )
        print "ps lines:"
        for p in psread:
            print p
        print len(psread)
        assert(len(psread)==2*n) # once wrapped with chmod 777, once by itself.
    def testSSHLeaveStamp(self):
        """testSSHLeaveStamp: leave a single stampfile"""
        nsleep = 4; taskid = RandomID()
        taccpool = DefaultHostPool(commandexecutor=SSHExecutor())
        start = time.time()
        t = RandomSleepTask(taskid=taskid,t=nsleep,stamproot=self.stampname,debug="task")
        nodepool = taccpool.request_nodes(1)
        assert(nodepool is not None)
        print "available pool:",str(nodepool)
        assert(nodepool.offset==0)
        t.start_on_nodes(pool=nodepool)
        taccpool.occupyNodes(nodepool,t.taskid)
        time.sleep(nsleep+1)
        curdir = t.completion.stampdir; dircontent = os.listdir(curdir)
        print "looking for stamps in <<%s>> and found <<%s>>" % \
            (curdir,sorted(dircontent))
        stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
        print "stamps:",sorted(stamps)
        wanted = self.stampname+str(taskid); print "wanted:",wanted
        assert(wanted in stamps)
    def testSSHLeaveStampLoop(self):
        """testSSHLeaveStampLoop: make sure tasks leave a stampfile"""
        ntasks = 7; nsleep = 5
        taccpool = DefaultHostPool(commandexecutor=SSHExecutor())
        if ntasks<len(taccpool): # just to make sure we can run this
            start = time.time()
            for itask in range(ntasks):
                t = RandomSleepTask(taskid=itask,t=nsleep,stamproot=self.stampname)
                nodepool = taccpool.request_nodes(1)
                if nodepool is None:
                    assert(False) # there should be enough nodes open
                print "available pool:",str(nodepool)
                assert(nodepool.offset==itask)
                t.start_on_nodes(pool=nodepool)
                taccpool.occupyNodes(nodepool,t.taskid)
            interval = time.time()-start; print "this took %e seconds" % interval
            assert(interval<ntasks*.5)
            time.sleep(nsleep+1)
            dir = t.completion.stampdir; dircontent = os.listdir(dir)
            print "looking for stamps and found:",sorted(dircontent)
            stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
            print "stamps:",sorted(stamps)
            assert(len(stamps)==ntasks)
        else: assert(True)
    def testSSHLeaveLocalResult(self):
        """testSSHLeaveLocalResult: create a file and detect that it's there"""
        nsleep = 2; taskid = RandomID()
        taccpool = DefaultHostPool(commandexecutor=SSHExecutor())
        start = time.time()
        tmpfile = RandomFile()
        t = Task( Commandline("touch %s" % tmpfile),taskid=taskid,
                 completion=FileCompletion(taskid=taskid),debug="task")
        nodepool = taccpool.request_nodes(1)
        assert(nodepool is not None)
        t.start_on_nodes(pool=nodepool)
        taccpool.occupyNodes(nodepool,t.taskid)
        time.sleep(nsleep+1)
        assert(t.completion.test())
        print "stampdir:",sorted(os.listdir(t.completion.stampdir))
        dircontent = os.listdir(os.getcwd())
        print "looking for result locally and found <<%s>>" % sorted(dircontent)
        assert(tmpfile in dircontent)
    def testSSHLeaveStampLoop(self):
        """testSSHLeaveStampLoop: make sure tasks leave a stampfile"""
        ntasks = 7; nsleep = 5
        taccpool = DefaultHostPool(commandexecutor=SSHExecutor())
        if ntasks<len(taccpool): # just to make sure we can run this
            start = time.time()
            for itask in range(ntasks):
                t = RandomSleepTask(taskid=itask,t=nsleep,stamproot=self.stampname)
                nodepool = taccpool.request_nodes(1)
                if nodepool is None:
                    assert(False) # there should be enough nodes open
                print "available pool:",str(nodepool)
                assert(nodepool.offset==itask)
                t.start_on_nodes(pool=nodepool)
                taccpool.occupyNodes(nodepool,t.taskid)
            interval = time.time()-start; print "this took %e seconds" % interval
            assert(interval<ntasks*.5)
            time.sleep(nsleep+1)
            dir = t.completion.stampdir; dircontent = os.listdir(dir)
            print "looking for stamps and found:",sorted(dircontent)
            stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
            print "stamps:",sorted(stamps)
            assert(len(stamps)==ntasks)
        else: assert(True)
    def testRemoteSSHEnv(self):
        """testRemoteSSHEnv: This tests whether the environment is propagated.
        We set an environment variable, and start a process that prints it.
        """
        hosts = DefaultHostPool().unique_hostnames()
        if len(hosts)>1:
            print "available hosts:",hosts
            self.setup()
            pool = HostPool(hostlist=HostList([hosts[1]]),
                            commandexecutor=SSHExecutor())
            var = RandomFile()+"_var"; val = str( RandomID() ); os.environ[var] = val
            fn = "testremotessh"; fn = os.getcwd()+"/"+fn
            t = Task( Commandline("echo $%s > %s; sleep 1" % (var,fn)),
                      debug="task+exec+ssh")
            t.start_on_nodes(pool=HostLocator(pool=pool,extent=1,offset=0))
            time.sleep(1)
            if ClusterHasSharedFileSystem():
                try:
                    with open(fn) as outfile:
                        for line in outfile:
                            line = line.strip(); print "<<%s>>" % line
                            assert(line==val)
                            break
                except: 
                    assert(False)
            else:
                command = "cat %s/%s" % (pwd,fn)
                p = subprocess.Popen(command,shell=True,stdout=subprocess.PIPE)
                hostread = p.communicate()[0].strip(); print hostread
                assert(hostread==val)
            os.system("/bin/rm -f %s" % fn)
        else: assert(True)

class testLeaveSSHOutput():
    def setup(self):
        ndirs = 3
        self.dirs = [ RandomDir() for d in range(ndirs) ]
        print "creating directories:",self.dirs,"in",os.getcwd()
        for d in self.dirs:
            absdir = os.getcwd()+"/"+d
            if os.path.isfile(absdir):
                raise LauncherException("Problem running this test")
            if os.path.isdir(absdir):
                shutil.rmtree(absdir)
            print "creating",absdir
            os.mkdir(absdir)
        tmpdir = os.getcwd()+"/"+Executor.default_workdir
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir)
        self.taccpool = DefaultHostPool(commandexecutor=SSHExecutor())
    def teardown(self):
        for d in self.dirs:
            if os.path.isdir(d):
                shutil.rmtree(d)            
    def testSSHLeaveResultAbsolute(self):
        """testSSHLeaveResultAbsolute: create a file in a directory and detect that it's there"""
        print "curdir  :",sorted(os.listdir(os.getcwd()))
        print "available",self.dirs
        taskid = RandomID()
        start = time.time()
        tmpdir = self.dirs[0]; tmpfile = RandomFile(); absdir = os.getcwd()+"/"+tmpdir
        print "going to create %s in %s" % (tmpfile,tmpdir)
        t = Task( Commandline("cd %s; touch %s" % (absdir,tmpfile)),
                  taskid=taskid,
                  completion=FileCompletion(taskid=taskid),debug="task+exec+ssh")
        nodepool = self.taccpool.request_nodes(1)
        assert(nodepool is not None)
        t.start_on_nodes(pool=nodepool)
        self.taccpool.occupyNodes(nodepool,t.taskid)
        time.sleep(1)
        assert(t.completion.test())
        print "stampdir:",sorted(os.listdir(t.completion.stampdir))
        dircontent = os.listdir(absdir)
        print "looking for result in <<%s>> and found <<%s>>" % \
            (absdir,sorted(dircontent))
        assert(tmpfile in dircontent)
    def testSSHLeaveResultRelative(self):
        """testSSHLeaveResultRelative: create a file in a directory and detect that it's there"""
        print "curdir  :",sorted(os.listdir(os.getcwd()))
        print "available",self.dirs
        taskid = RandomID()
        start = time.time()
        tmpdir = self.dirs[0]; tmpfile = RandomFile(); absdir = os.getcwd()+"/"+tmpdir
        print "going to create %s in %s" % (tmpfile,tmpdir)
        t = Task( Commandline("cd %s; touch %s" % (tmpdir,tmpfile)),
                  taskid=taskid,
                  completion=FileCompletion(taskid=taskid),debug="task+exec+ssh")
        nodepool = self.taccpool.request_nodes(1)
        assert(nodepool is not None)
        t.start_on_nodes(pool=nodepool)
        self.taccpool.occupyNodes(nodepool,t.taskid)
        time.sleep(1)
        assert(t.completion.test())
        print "stampdir:",sorted(os.listdir(t.completion.stampdir))
        dircontent = os.listdir(absdir)
        print "looking for result in <<%s>> and found <<%s>>" % \
            (absdir,sorted(dircontent))
        assert(tmpfile in dircontent)
    def testLeaveModResultsImmediately(self):
        """testLeaveModResultsImmediately: Leave results in multiple directories"""
        ntasks = len(self.taccpool)
        tasks = TaskGenerator( 
            [ "cd %s ; touch f%d" % (self.dirs[ i%len(self.dirs) ],i) 
              for i in range(ntasks) ],
            )
        collected = []
        for t in TaskGeneratorIterate( tasks ):
            nodes = self.taccpool.request_nodes(1)
            t.start_on_nodes(pool=nodes)
            collected.append(t)
        time.sleep(1)
        for t in collected:
            assert(t.completion.test())
        for d in self.dirs:
            content = os.listdir(d)
            assert(len(content)>=int(ntasks/len(self.taccpool)))
    def testLeaveModResultsWithTest(self):
        """testLeaveModResultsWithTest: Leave results in multiple directories with stamptest"""
        ntasks = len(self.taccpool)
        # leave stamps in the first tmp directory
        tasks = TaskGenerator( 
            [ "cd %s ; touch f%d" % (self.dirs[ i%len(self.dirs) ],i) 
              for i in range(ntasks) ],
            completion=lambda x:FileCompletion(taskid=x,stampdir=self.dirs[0]),
            )
        collected = []
        for t in TaskGeneratorIterate( tasks ):
            nodes = self.taccpool.request_nodes(1)
            t.start_on_nodes(pool=nodes)
            collected.append(t)
        time.sleep(1)
        for t in collected:
            assert(t.completion.test())
        for d in self.dirs[1:]:
            content = os.listdir(d)
            assert(len(content)>=int(ntasks/len(self.taccpool)))
        content0 = os.listdir(self.dirs[0]); print sorted(content0)
        stamps = [ f for f in content0 if re.search("expire",f) ]
        assert(len(stamps)==ntasks)


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
        stdout = kwargs.pop("stdout",subprocess.PIPE)
        full_commandline =  "ibrun -o %d -n %d %s & " % \
               (pool.offset,pool.extent,self.wrap(command))
        DebugTraceMsg("executed commandline: <<%s>>" % full_commandline,
                      self.debug,prefix="Exec")
        p = subprocess.Popen(full_commandline,
                             shell=True,stdout=stdout)
        self.popen_object = p
    def terminate(self):
        if self.popen_object is not None:
            self.popen_object.terminate()

class testIbrunExecutor():
    def setup(self):
        """This creates and compiles a MPI program.
        The program outputs the hostname and the communicator size."""
        self.testprog_name = "pylauncher_tmp_prog_print_comm_size"
        testprog = open(self.testprog_name+".c","w")
        testprog.write("""
#include <stdlib.h>
#include <stdio.h>
#include "mpi.h"
int main(int argc,char **argv) {
  int mytid,ntids;
  MPI_Init(&argc,&argv);
  MPI_Comm_rank(MPI_COMM_WORLD,&mytid);
  MPI_Comm_size(MPI_COMM_WORLD,&ntids);
  if (mytid==0) printf("TACC PyLauncher comm size detection running\\n");
  if (mytid==0) system("hostname -f");
  if (mytid==0) printf("%d\\n",ntids);
  MPI_Finalize();
  return 0;
}
""")
        testprog.close()
        os.system("mpicc -o %s %s.c" % (self.testprog_name,self.testprog_name))
        os.system("/bin/rm -rf %s" % Executor.default_workdir)
    def testIbrunNodeOccupy(self):
        """testIbrunNodeOccupy: put two parallel tests on the host pool;
        one each on half of the pool."""
        self.workdir = MakeRandomDir()
        ibrun_executor = IbrunExecutor(debug="exec",workdir=self.workdir)
        pool = DefaultHostPool(commandexecutor=ibrun_executor)
        if len(pool)%2==1:
            raise LauncherException("Default hostpool <<%s>> has odd length" \
                                    % str( [ str(n.hostname) for n in pool.nodes ] ) )
        nnodes = len(pool)/2
        nslp = 4
        # put a task on half the nodes
        line1 = os.getcwd()+"/"+self.testprog_name
        nodes1 = pool.request_nodes(nnodes)
        print "line1:", line1
        out1 = RandomFile(); out_handle1 = open(out1,"w")
        ibrun_executor.execute(line1,pool=nodes1,stdout=out_handle1)
        pool.occupyNodes(nodes1,1)
        # put a task on the other half of the nodes
        line2 = os.getcwd()+"/"+self.testprog_name
        nodes2 = pool.request_nodes(nnodes)
        print "line2:", line2
        out2 = RandomFile(); out_handle2 = open(out2,"w")
        ibrun_executor.execute(line2,pool=nodes2,stdout=out_handle2)
        pool.occupyNodes(nodes2,2)
        # there should be no nodes left
        no_nodes = pool.request_nodes(1); print no_nodes
        assert(no_nodes is None)
        # see if the result was left
        time.sleep(nslp)
        assert( os.path.isfile(out1) )
        with open(out1,"r") as output1:
            t = 0
            for line in output1:
                line = line.strip()
                print "output1:",line
                if re.match("TACC",line): continue
                t += 1
                if t==1: hostname1 = line
                if t==2: assert(int(line)==nnodes)                
                break
        assert( os.path.isfile(out2) )
        with open(out2,"r") as output2:
            t = 0
            for line in output2:
                line = line.strip()
                print "output2:",line
                if re.match("TACC",line): continue
                t += 1
                if t==1: hostname2 = line
                if t==2: assert(int(line)==nnodes)                
                break
        if len(pool.unique_hostnames())>1:
            assert(hostname1!=hostname2)
        pool.release()
        # see what's running
        # host1 = nodes1.firsthost()
        # host2 = nodes2.firsthost()
        # ssh1 = ssh_client(host1)
        # ssh2 = ssh_client(host2)


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
        self.debugs = kwargs.pop("debug","")
        self.hostpool = kwargs.pop("hostpool",None)
        if self.hostpool is None:
            raise LauncherException("Need a host pool")
        self.workdir = kwargs.pop("workdir",".")
        DebugTraceMsg("Host pool: <<%s>>" % str(self.hostpool),
                      re.search("host",self.debugs),"Job")
        self.taskgenerator = kwargs.pop("taskgenerator",None)
        if self.taskgenerator is None:
            raise LauncherException("Need a task generator")
        self.delay = kwargs.pop("delay",.5)
        self.queue = TaskQueue(debug=self.debugs)
        self.maxruntime = kwargs.pop("maxruntime",0)
        self.taskmaxruntime = kwargs.pop("taskmaxruntime",0)
        self.debug = re.search("job",self.debugs)
        self.completed = 0; self.aborted = 0; self.tock = 0; self.barriertest = None
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
    def tick(self):
        """This routine does a single time step in a launcher's life, and reports back
        to the user. Specifically:

        * It tries to start any currently queued jobs. Also:
        * If any jobs are finished, it detects exactly one, and reports its ID to the user in a message ``expired 123``
        * If there are no finished jobs, it invokes the task generator; this can result in a new task and the return message is ``continuing``
        * if the generator stalls, that is, more tasks will come in the future but none are available now, the message is ``stalling``
        * if the generator is finished and all jobs have finished, the message is ``finished``

        After invoking the task generator, a short sleep is inserted (see the ``delay`` parameter)
        """
        DebugTraceMsg("\ntick %d\nQueue:\n%s" % (self.tock,str(self.queue)),self.debug)
        self.tock += 1
        # see if the barrier test is completely satisfied
        if self.barriertest is not None:
            if reduce( lambda x,y: x and y,
                       [ t.completed() for t in self.barriertest ] ):
                self.barriertest = None
                message = "continuing"
            else:
                # if the barrier still stands, stall
                message = "stalling"
        else:
            # if the barrier is resolved, queue and test and whatnot
            self.queue.startQueued(self.hostpool,starttick=self.tock)
            message = None

            self.handle_completed()
            self.handle_aborted()
            message = self.handle_enqueueing()
            #if message in ["stalling","continuing"]:
            time.sleep(self.delay)

        if re.search("host",self.debugs):
            DebugTraceMsg(str(self.hostpool))
        DebugTraceMsg("status: %s" % message,self.debug,prefix="Job")
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
        try:
            task = self.taskgenerator.next()
            if task==pylauncherBarrierString:
                message = "stalling"
                self.barriertest = [ t.completion for t in self.queue.running ]
                DebugTraceMsg("barrier encountered",self.debug,prefix="Job")
            elif task=="stall":
                message = "stalling"
                DebugTraceMsg("stalling",self.debug,prefix="Job")
            else:
                self.enqueue_task(task)
                message = "enqueueing"
        except:
            message = self.finish_or_continue()
        return message
    def post_process(self,taskid):
        DebugTraceMsg("Task %s expired" % str(taskid),self.debug,prefix="Job")
    def run(self):
        """Invoke the launcher job, and call ``tick`` until all jobs are finished."""
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
            res = self.tick()
            # update the restart file
            state_f = open(self.workdir+"/queuestate","w")        
            state_f.write( self.queue.savestate() )
            state_f.close()
            # process the result
            # if re.match("expired",res):
            #     self.post_process( res.split(" ",1)[1] )
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
""" % ( self.runningtime, self.queue.final_report(), self.hostpool.final_report() )
        return message


class TestLocalLauncherJobs():
    """Tests of the LauncherJob class through the LocalExecutor,
    which is the default for the HostPool class"""
    def removecommandfile(self):
        os.system("rm -f %s" % self.fn)
    def setup(self):
        self.launcherdir = MakeRandomDir()
        self.makecommandfile() # this sets self.ncommand
        self.hostpool = LocalHostPool(nhosts=self.ncommand,workdir=self.launcherdir)
    def makecommandfile(self):
        """make a commandlines file"""
        self.fn = "unittestlines"; self.ncommand = 6; self.maxsleep = 4
        MakeRandomSleepFile( self.fn,self.ncommand,
                             tmin=self.maxsleep, tmax=self.maxsleep )
        self.icommand = 0; 
    def testLocalFileTaskJob(self):
        """testLocalFileTaskJob: test instantaneously finished jobs on a local hostpool"""
        ntasks = self.ncommand
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=1) ),
            hostpool=self.hostpool, delay=.2, debug="queue,job"
            )
        starttime = time.time()
        while True:
            res = job.tick()
            elapsed = time.time()-starttime
            print "tick:",job.tock,"elapsed: %5.3e" % elapsed,"result:",res
            if res=="finished": break
            elif re.match("^expire",res):
                print res
            if elapsed>2+ntasks*job.delay+self.maxsleep:
                estr = "This is taking too long: %d sec for %d tasks" % (int(elapsed),ntasks)
                print estr
                raise LauncherException(estr)
        assert(True)
    def testLocalFileTaskJobCustom(self):
        """testLocalFileTaskJobCustom: test jobs with file completion on a local pool"""
        ntasks = self.ncommand
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=1),
                      completion=lambda x:FileCompletion(taskid=x,
                                            stampdir=self.launcherdir,stamproot="expire"),
                                         debug="task"),
            delay=1,
            hostpool=self.hostpool, debug="queue,job,task"
            )
        starttime = time.time()
        while True:
            res = job.tick()
            assert( os.path.isdir(self.launcherdir) )
            elapsed = time.time()-starttime
            print "tick:",job.tock,"elapsed: %5.3e" % elapsed,"result:",res
            if res=="finished": break
            elif re.match("^expire",res):
                print res
            if elapsed>2+ntasks*job.delay+self.maxsleep:
                estr = "This is taking too long: %d sec for %d tasks" % (int(elapsed),ntasks)
                print estr
                raise LauncherException(estr)
        if elapsed<self.maxsleep:
            print "This finished too quickly: %d s/b %d" % (elapsed,self.maxsleep)
            assert(False)
        assert(True)

class TestExistingWorkdir():
    def setup(self):
        self.fn = RandomFile()
        # working directory
        self.tmpdir = NoRandomDir()
        self.launcherdir = self.tmpdir
    def makehostpool(self):
        self.hostpool = DefaultHostPool(
            commandexecutor=SSHExecutor(workdir=self.tmpdir))
        self.ncores = len(self.hostpool)
    def makecommandfile(self,ncommand):
        self.ncommand = ncommand; self.maxsleep = 4
        print "Making %d commands" % ncommand
        self.removecommandfile()
        MakeRandomSleepFile( self.fn,self.ncommand,
                             tmin=self.maxsleep,tmax=self.maxsleep)
    def teardown(self):
        self.removecommandfile()
    def removecommandfile(self):
        os.system("rm -f %s" % self.fn)
    def test_1_NoDoubleRun(self):
        self.makehostpool()
        ntasks = 2*self.ncores
        self.makecommandfile(ncommand=ntasks)
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=1),
                   completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir),
                                         debug="task"),
            hostpool=self.hostpool,workdir=self.launcherdir,
            delay=.1, debug="queue,job",
            maxruntime = self.maxsleep+1
            )
        job.run()
        try:
            self.makehostpool()
            job = LauncherJob( 
                taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=1),
                     completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir),
                                             debug="task"),
                hostpool=self.hostpool,workdir=self.launcherdir,
                delay=.1, debug="queue,job",
                maxruntime = self.maxsleep+1
                )
            job.run()
            print "Hm. We managed to reuse a workdir"
            result = False # this should except out becuase of the workdir
        except: 
            print "Exception: attempting to reuse workdir"
            result = True
        assert(result)

class fooTestBreakRestart():
    def setup(self):
        self.fn = RandomFile()
        # working directory
        tmpdir = NoRandomDir()
        self.launcherdir = tmpdir
        self.hostpool = DefaultHostPool(commandexecutor=SSHExecutor(workdir=tmpdir))
        self.ncores = len(self.hostpool)
    def makecommandfile(self,ncommand):
        self.ncommand = ncommand; self.maxsleep = 4
        print "Making %d commands" % ncommand
        self.removecommandfile()
        MakeRandomSleepFile( self.fn,self.ncommand,
                             tmin=self.maxsleep,tmax=self.maxsleep)
    def teardown(self):
        self.removecommandfile()
    def removecommandfile(self):
        os.system("rm -f %s" % self.fn)
    def test_2_Break(self):
        ntasks = 2*self.ncores
        self.makecommandfile(ncommand=ntasks)
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=1),
                   completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir),
                                         debug="task"),
            hostpool=self.hostpool,workdir=self.launcherdir,
            delay=.1, debug="queue,job",
            maxruntime = self.maxsleep+1
            )
        job.run()
        print job.final_report()
        completed = job.queue.completed
        noncomp = job.queue.running+job.queue.queue
        print "lengths of completed / noncomp",len(completed),len(noncomp)
        # assert(len(completed)==self.ncores) ## this is not easily predicted
        assert(len(noncomp)>0)
        assert(len(completed)+len(noncomp)==ntasks)
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=1),
                   skip=completed,
                   completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir),#reusestampdir
                                         debug="task"),
            hostpool=self.hostpool,workdir=self.launcherdir,#reuseworkdir?
            delay=.1, debug="queue,job",
            )
        job.run()
        assert(True)

class TestSSHLauncherJobs():
    """Tests of the LauncherJob class through the SSHExecutor"""
    def removecommandfile(self):
        os.system("rm -f %s" % self.fn)
    def makecommandfile(self,cores=1,ncommand=6):
        """make a commandlines file"""
        self.fn = "unittestlines"; self.ncommand = ncommand
        self.maxsleep = 5; self.tmin = 3
        MakeRandomSleepFile( self.fn,self.ncommand,
                             tmax=self.maxsleep,tmin=self.tmin,
                             cores=cores )
        self.icommand = 0; 
    def setup(self):
        tmpdir = NoRandomDir()
        self.launcherdir = tmpdir
        self.hostpool = DefaultHostPool(commandexecutor=SSHExecutor(workdir=tmpdir))
    def teardown(self):
        os.system( "/bin/rm -rf %s" % self.launcherdir )
        self.removecommandfile()
    def testSSHFileTaskJob(self):
        """testSSHFileTaskJob: test ssh'ing on an actual host pool"""
        self.makecommandfile()
        ntasks = self.ncommand
        if ntasks>len(self.hostpool): # make sure we can run without delay
            assert(True); return
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=1),
                      completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir) ),
            hostpool=self.hostpool,
            delay=.2, debug="queue,job"
            )
        starttime = time.time()
        while True:
            res = job.tick()
            elapsed = time.time()-starttime
            print "tick:",job.tock,"elapsed: %5.3e" % elapsed,"result:",res
            if res=="finished": break
            elif re.match("^expire",res):
                print res
            if elapsed>2+ntasks*job.delay+self.maxsleep:
                estr = "This is taking too long: %d sec for %d tasks" % (int(elapsed),ntasks)
                print estr
                assert(False)
        duration = time.time()-starttime; print duration
        assert(duration>=self.tmin)
    def testLauncherJobRun(self):
        """testLauncherJobRun: test with ssh'ing, and just let it run"""
        self.makecommandfile()
        ntasks = self.ncommand; delay = .2
        if ntasks>len(self.hostpool): # make sure we can run without delay
            assert(True); return
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=1),
                              completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir) ),
            hostpool=self.hostpool,
            delay=delay,maxruntime=self.maxsleep+ntasks*delay+2,
            debug="queue,job"
            )
        starttime = time.time()
        job.run()
        duration = time.time()-starttime; print duration
        assert(duration>=self.tmin)
    def testMulticoreTaskGenerator(self):
        """testMulticoreTaskGenerator: This is preliminary to the next test"""
        ncores = 2
        self.makecommandfile(cores=ncores)
        ntasks = int( self.ncommand/ncores ); delay = .2
        if ntasks>len(self.hostpool)/ncores: # make sure we can run without delay
            assert(True); return
        generator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=ncores),
                    completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir),
                                 debug="task")
        for t in generator:
            if t in ["stall","stop"]:
                break
            assert( t.size==ncores )
        assert(True)
    def testMulticoreLauncherJobRun(self):
        """testMulticoreLauncherJobRun: test with ssh'ing, and just let it run"""
        ncores = 2
        self.makecommandfile(cores=ncores)
        ntasks = int( self.ncommand/ncores ); delay = .2
        # if ntasks>len(self.hostpool)/ncores: # make sure we can run without delay
        #     assert(True); return
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=ncores),
                              completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir),
                                         debug="task"),
            hostpool=self.hostpool, delay=delay, maxruntime=self.maxsleep+ntasks*delay+2,
            debug="queue,job"
            )
        starttime = time.time()
        job.run()
        duration = time.time()-starttime; print duration
        assert(duration>=self.tmin)
    def testLauncherJobRunWithWait(self):
        ntasks = 2*len(self.hostpool); delay = .2
        self.makecommandfile(ncommand=ntasks)
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=1),
                      completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir) ),
            hostpool=self.hostpool,
            delay=delay,maxruntime=2*self.maxsleep+ntasks*delay+2,
            debug="queue,job"
            )
        job.run()
        print "tasks completed %d s/b %d" % (job.completed,self.ncommand)
        assert(job.completed==self.ncommand)

class testIBRUNLauncherJobs():
    def setup(self):
        self.launcherdir = NoRandomDir()
        self.hostpool = HostPool( hostlist=HostListByName(),
                 commandexecutor=IbrunExecutor(workdir=self.launcherdir,debug="exec,ssh"),
                                  debug="host,task")
        self.makecommandfile()
    def teardown(self):
        self.hostpool.release()
    def makecommandfile(self):
        """make a commandlines file"""
        self.fn = RandomFile("ibruntest"); self.ncommand = 6; self.maxsleep = 4
        self.outfile = RandomFile("ibruntest-out")
        os.system("rm -f %s %s" % (self.fn,self.outfile) )
        #MakeRandomSleepFile( self.fn,self.ncommand,tmax=self.maxsleep )
        MakeRandomCommandFile\
            (self.fn,self.ncommand,
             generator=CountedCommandGenerator(
                    command="/bin/true",nmax=self.ncommand) #,catch=self.outfile))
             )
        self.icommand = 0; 
    def testIbrunFileTaskJobSingle(self):
        """testIbrunFileTaskJobSingle: test ssh'ing on an actual host pool"""
        ntasks = self.ncommand
        if 2*ntasks>len(self.hostpool): # make sure we can run without delay
            assert(True); return 
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=2),
                 completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir),
                                         debug="task"),
            hostpool=self.hostpool,delay=.2,
            debug="queue,job,task,exec"
            )
        starttime = time.time()
        while True:
            res = job.tick()
            elapsed = time.time()-starttime
            print "tick:",job.tock,"elapsed: %5.3e" % elapsed,"result:",res
            if res=="finished": break
            elif re.match("^expire",res):
                print res
            if elapsed>2+ntasks*job.delay+self.maxsleep:
                estr = "This is taking too long: %d sec for %d tasks" % (int(elapsed),ntasks)
                print estr
                assert(False)
        assert(True)
    def testIbrunFileTaskJob(self):
        """testIbrunFileTaskJob: test ssh'ing on an actual host pool"""
        ntasks = self.ncommand
        if 2*ntasks>len(self.hostpool): # make sure we can run without delay
            assert(True); return 
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=2),
                      completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir) ),
            hostpool=self.hostpool,delay=.2,
            debug="queue,job"
            )
        starttime = time.time()
        while True:
            res = job.tick()
            elapsed = time.time()-starttime
            print "tick:",job.tock,"elapsed: %5.3e" % elapsed,"result:",res
            if res=="finished": break
            elif re.match("^expire",res):
                print res
            if elapsed>2+ntasks*job.delay+self.maxsleep:
                estr = "This is taking too long: %d sec for %d tasks" % (int(elapsed),ntasks)
                print estr
                assert(False)
        assert(True)
    def testLauncherJobIbRun(self):
        """testLauncherJobIbRun: test with ssh'ing, and just let it run"""
        ntasks = self.ncommand; delay = .2
        if 2*ntasks>len(self.hostpool): # make sure we can run without delay
            assert(True); return
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,cores=2),
                      completion=lambda x:FileCompletion(taskid=x,stampdir=self.launcherdir) ),
            hostpool=self.hostpool,
            delay=delay,maxruntime=self.maxsleep+ntasks*delay+2,
            debug="queue,job"
            )
        job.run()
        assert(True)

def testChDir():
    tmpdir = "pylauncher_tmpdir_test%d" % RandomID(); tmpfile = RandomFile()
    abs_tmpdir = os.getcwd()+"/"+tmpdir; print "working dir:",abs_tmpdir
    os.system("rm -rf %s" % abs_tmpdir)
    os.system("mkdir -p %s" % abs_tmpdir)
    os.chdir(tmpdir)
    job = LauncherJob( 
      hostpool=LocalHostPool(debug="exec"),
      taskgenerator=TaskGenerator( 
            ListCommandlineGenerator(list=["pwd ; echo foo ; echo bar > %s " % tmpfile ]),
            debug="task",
            ),
      debug="task+queue+exec")
    job.run(); time.sleep(1)
    dircontent = os.listdir("."); print ". :",sorted(dircontent)
    dircontent = os.listdir(".."); print ".. :",sorted(dircontent)
    dircontent = os.listdir(abs_tmpdir); print abs_tmpdir,":",sorted(dircontent)
    assert(tmpfile in dircontent)
    os.system("rm -rf %s" % abs_tmpdir)

def testParamJob():
    # first make a C program that parses its argument
    testdir = MakeRandomDir()
    testprog_name = "print_program"
    print "Making c program <<%s>> in <<%s>>" % (testprog_name,testdir)
    os.system("pwd")
    with open( os.path.join(testdir,testprog_name+".c"),'w') as testprog:
        testprog.write("""
#include <stdlib.h>
#include <stdio.h>
int main(int argc,char **argv) {
  int id = atoi(argv[0]);
  printf(\"id: %d\\n\",id);
  return 0;
}
""")
    os.system("cd %s && mpicc -o %s %s.c" % (testdir,testprog_name,testprog_name))
    ###??? os.system("/bin/rm -rf %s" % Executor.default_workdir)
    #
    # fn = RandomFile(); ntask = 10
    # with open(fn,"w") as commandfile:
    #     for i in range(ntask):
    #         commandfile.write("./%s PYLID\n" % testprog_name)
    # FileCommandlineGenerator(testprog)
    # os.system("rm -f %s" % testprog_name)
    ntasks = 10; catchfile = RandomFile()
    job = LauncherJob( 
      hostpool=LocalHostPool(debug="exec"),
      taskgenerator=TaskGenerator( 
            ListCommandlineGenerator(
                list=["./%s PYLID" % testprog_name for i in range(ntasks) ]),
            debug="task",
            ),
      gather_output=catchfile,
      debug="task+queue+exec")
    job.run(); time.sleep(1)
    os.system("rm -f %s*" % testprog_name)
    assert(True)

# def testDependencies():
#     ntasks = 4; nsleep = 4
#     launcherdir = RandomDir(); os.system("/bin/rm -rf %s" % launcherdir)
#     hostpool = LocalHostPool(
#         nhosts=2*ntasks,workdir=launcherdir,force_workdir=True)
#     fn = RandomFile(); comms = SleepCommandGenerator(tmin=nsleep,tmax=nsleep)
#     commandfile = open( fn, "w")
#     for i in range(ntasks):
#         commandfile.write( "1,%d,%s\n" % (i,comms.next()) )
#     commandfile.write( "1,%d-%d:%d,%s" % \
#               ( ntasks,0,ntasks,
#                 comms.next() ) )
#     commandfile.close()
#     os.system("cat %s" % fn)
#     tstart = time.time()
#     job = LauncherJob( hostpool=hostpool,
#       taskgenerator=TaskGenerator( 
#             FileCommandlineGenerator( fn,cores="file",dependencies=True ),
#             debug="task",
#             ),
#       debug="task+queue+exec")
#     job.run()
#     runtime = time.time()-tstart; print nsleep,runtime
#     assert(runtime>2*nsleep)

def ClassicLauncher(commandfile,*args,**kwargs):
    """A LauncherJob for a file of single or multi-threaded commands.

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
        hostpool=HostPool( hostlist=HostListByName(),
            commandexecutor=SSHExecutor(workdir=workdir,debug=debug), debug=debug ),
        taskgenerator=TaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            completion=lambda x:FileCompletion( taskid=x,
                                    stamproot="expire",stampdir=workdir),
            debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print job.final_report()

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
        taskgenerator=TaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            completion=lambda x:FileCompletion(taskid=x,
                                      stamproot="expire",stampdir=workdir),
            debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print job.final_report()

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
        hostpool=HostPool( hostlist=HostListByName(),
            commandexecutor=IbrunExecutor(workdir=workdir,debug=debug), debug=debug ),
        taskgenerator=TaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            completion=lambda x:FileCompletion(taskid=x,
                                      stamproot="expire",stampdir=workdir),
            debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print job.final_report()

class DynamicLauncher(LauncherJob):
    """A LauncherJob derived class that is designed for dynamic adding of 
    commands. This should make it easier to integrate
    in environments that expect to "submit" jobs one at a time.

    This has two extra methods:
    * append(commandline) : add commandline to the internal queue
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
            HostPool( hostlist=HostListByName(),
                      commandexecutor=SSHExecutor(workdir=workdir,debug=debug), 
                      debug=debug ))
        workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
        cores = kwargs.pop("cores",1)
        LauncherJob.__init__(self,
            hostpool=hostpool,
            taskgenerator=TaskGenerator( 
                DynamicCommandlineGenerator(commandfile,cores=cores,debug=debug),
                completion=lambda x:FileCompletion( taskid=x,
                                        stamproot="expire",stampdir=workdir),
                debug=debug ),
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
        hostpool=HostPool( hostlist=HostListByName(),
            commandexecutor=LocalExecutor(
                prefix="/bin/sh ",workdir=workdir,debug=debug), 
                           debug=debug ),
        taskgenerator=TaskGenerator( 
            FileCommandlineGenerator(commandfile,cores=cores,debug=debug),
            completion=lambda x:FileCompletion( taskid=x,
                                    stamproot="expire",stampdir=workdir),
            debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print job.final_report()

if __name__=="__main__":
    testPEhostpools()
    t = testPermanentSSHconnection()
    t.setup(); t.testRemoteSSH()
    pass

## TestBreakRestart disabled
