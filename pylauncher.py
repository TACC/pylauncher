"""pylauncher.py version 1.5 2012/10/09

A python based launcher utility for packaging sequential or
low parallel jobs in one big parallel job

Author: Victor Eijkhout
eijkhout@tacc.utexas.edu

Change log
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
import os
import re
import stat
import shutil
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
    debugtracefile = open(launcherdir+"/debugtracefile","w",1)
runtime = time.time()
def DebugTraceMsg(msg,sw=False):
    if not sw: return
    if msg[0]=="\n":
        print
        msg = msg[1:]
    print "[t=%5.3f] %s" % (time.time()-runtime,msg)
    if debugtracefile is not None:
        debugtracefile.write(msg+"\n")
        os.fsync()
def CloseDebugtracefile():
    close(debugtracefile)

class CommandGenerator():
    def __init__(self,**kwargs):
        self.count = 0
        self.nmax = kwargs.pop("nmax",-1)
        self.catch = kwargs.pop("catch",None)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed CommandGenerator args: %s" % str(kwargs))
    def next(self):
        if self.count==self.nmax: raise StopIteration
        thecount = self.count; self.count += 1
        command = "echo %d" % thecount
        if self.catch is not None:
            command += " > %s 2>&1 " % self.catch
        return command
    def __iter__(self): return self
    def randomizeoutput(self):
        oldnext = self.next
        def newnext(self):
            if self.count % 3==2 and self.comment==0:
                self.comment = 1
                return "# comment before %d" % self.count
            return oldnext(self)
        self.next = newnext
        return self

def testComamndGenerator():
    ntasks = 15
    generator = CommandGenerator(nmax=ntasks)
    count = 0
    for g in generator:
        assert( re.match('echo',g) )
        count += 1
    assert(count==ntasks)

# def testRandomizedComamndGenerator():
#     ntasks = 6
#     generator = CommandGenerator(nmax=ntasks).randomizeoutput()
#     count = 0
#     for g in generator:
#         print g
#         count += 1
#     assert(count==ntasks+2)

class SleepCommandGenerator(CommandGenerator):
    def __init__(self,**kwargs):
        self.tmax = kwargs.pop("tmax",5)
        CommandGenerator.__init__(self,catch="/dev/null",**kwargs)
    def next(self):
        import random
        return CommandGenerator.next(self)+" ; sleep %d" % int(self.tmax*random.random())

def SingleSleepCommand(t):
    """this should not be called in a loop: only for single test"""
    return SleepCommandGenerator(nmax=1,tmax=t).next()

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

class CommandlineGenerator():
    """Generate a stream of << COMMAND "," CORECOUNT >> pairs.
    where corecount is a number and command is a unix command line."""
    def __init__(self,list,nmax=None):
        self.list = list; self.njobs = 0
        self.finished = False; self.stopped = False
        if nmax is None:
            self.nmax = len(list)
        else: self.nmax = nmax
    def finish(self): self.finished = True
    def next(self):
        """Different scenarios:
        nmax is None: exhaust the original list
        nmax > 0: keep popping from the list, stalling while it refills
        nmax == 0 : infinite, wait for someone to set the 'finished' flag"""
        if self.stopped:
            raise StopIteration
        elif self.finished or (self.nmax>0 and self.njobs==self.nmax) :
            # should this be if (list empty & finished)
            self.stopped = True
            return "stop",0
        elif len(self.list)>0:
            j = self.list[0]; self.list = self.list[1:]
            self.njobs += 1; return j
        else:
            return "stall",1
    def __iter__(self): return self

def testGeneratorList():
    gen = CommandlineGenerator([2,3,4])
    count = 0
    for g in gen:
        count += 1
    print "seen %d commands" % count
    assert(count==4)
def testGeneratorListAdd():
    gen = CommandlineGenerator([2,3,4],nmax=4)
    count = 0
    for g in gen:
        count += 1; gen.list.append(5) # this should be in an inherited class
    print "seen %d commands" % count
    assert(count==5)
def testGeneratorListFinish():
    gen = CommandlineGenerator([2,3,4],0)
    count = 0
    for g in gen:
        count += 1; gen.list.append(3*count)
        if count==6: gen.finish()
    print "seen %d commands" % count
    assert(count==7)
    
class FileCommandlineGenerator(CommandlineGenerator):
    def __init__(self,filename,cores=1):
        """A generator for commandline files:
        cores is 1 by default, other constants allowed.
        value cores="file" means the file has << count,command >> lines;
        blank lines and lines starting with the comment character `#' are ignored

        ??? This function should not be used directly: instead use the 
        TaskGenerator class which unifies task commands from files & dynamic objects??? """
        file = open(filename); commandlist = []
        for line in file.readlines():
            if re.match('^ *#',line) or re.match('^ *$',line):
                continue # skip blank and comment
            if cores=="file":
                c,l = line.strip().split(",",1)
            else:
                l = line.strip(); c = cores
            commandlist.append( [l,c] )
        CommandlineGenerator.__init__(self,commandlist)

def testFileCommandLineGenerator():
    fn = "fcltest"
    fh = open(fn,"w")
    for t in ["a","b","c","d"]:
        fh.write(t+"\n")
    fh.close()
    generator = FileCommandlineGenerator(fn)
    r,c = generator.next(); print r; assert(r=="a")
    r,c = generator.next(); print r; assert(r=="b")
    r,c = generator.next(); print r; assert(r=="c")
    r,c = generator.next(); print r; assert(r=="d")
    try:
        r,c = generator.next()
        assert(False)
    except:
        assert(True)

class DynamicCommandlineGenerator(CommandlineGenerator):
    """A CommandlineGenerator with an extra method:
    append: add a commandline to the list
    The 'nmax=0' parameter value makes the generator keep expecting new stuff.
    """
    def __init__(self,initial_list=[],nmax=0):
        CommandlineGenerator.__init__(self,[ a for a in initial_list ],nmax=nmax)
    def append(self,command,cores=1):
        self.list.append([command,cores])

def MakeRandomCommandFile(fn,ncommand,**kwargs):
    """make file with commandlines and occasional comments and blanks"""
    debug = kwargs.pop("debug",0)
    if debug==0:
        generator = kwargs.pop("generator",CommandGenerator(nmax=ncommand,catch="/dev/null"))
    else:
        generator = kwargs.pop("generator",CommandGenerator(nmax=ncommand))
    if len(kwargs)>0:
        raise LauncherException("Unprocessed args: %s" % str(kwargs))
    commandlines = open(fn,"w")
    for i in range(ncommand):
        if i%5==0:
            commandlines.write("# arbitrary comment\n")
        if i%7==0:
            commandlines.write("\n")
        c = generator.next()
        commandlines.write( c+"\n" )
    commandlines.close()

def MakeRandomSleepFile(fn,ncommand,**kwargs):
    """make file with sleep commandlines and occasional comments and blanks"""
    tmax = kwargs.pop("tmax",6)
    MakeRandomCommandFile\
        (fn,ncommand,generator=SleepCommandGenerator(nmax=ncommand,tmax=tmax),
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
        for l,c in FileCommandlineGenerator(self.fn,1):
            count += 1
        print "counted: %d, should be %d" % (count,self.ncommand+1)
        # with open(self.fn,"r") as f:
        #     for line in f:
        #         print line.strip()
        assert(count==self.ncommand+1)
        assert(l=="stop")
    def testDynamicCommandlineGeneratorMax(self):
        """testDynamicCommandlineGeneratorMax: generate commands until max"""
        nmax = 50
        generator = DynamicCommandlineGenerator(nmax=nmax)
        for count,command in enumerate(generator):
            generator.append(command)
        print count
        assert(count==nmax+1)
    def testDynamicCommandlineGeneratorInf(self):
        """testDynamicCommandlineGeneratorInf: generate commands until dynamic finish"""
        nmax = 60
        generator = DynamicCommandlineGenerator()
        for count,command in enumerate(generator):
            generator.append(command)
            if count==nmax:
                generator.finish()
        print count
        assert(count==nmax+1)

class Completion():
    def __init__(self,taskid=0):
        self.taskid = taskid
    def attach(self,txt):
        return txt
    def test(self):
        return True
class FileCompletion(Completion):
    stamproot = "expire"
    stampdir="."
    def __init__(self,**kwargs):
        taskid = kwargs.pop("taskid",-1)
        if taskid==-1:
            raise LauncherException("Need an explicit task ID")
        self.stamproot = kwargs.pop("stamproot",FileCompletion.stamproot)
        self.stampdir = kwargs.pop("stampdir",FileCompletion.stampdir)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed FileCompletion args: %s" % str(kwargs))
        # create stampdir. maybe this should be in the attach method?
        if self.stampdir[0]=="/":
            raise LauncherException("stampdirs have to be relative path")
        if not os.path.isdir(self.stampdir):
            os.makedirs(self.stampdir)
        Completion.__init__(self,taskid)
    def stampname(self):
        return "%s/%s%s" % (self.stampdir,self.stamproot,str(self.taskid))
    def attach(self,txt):
        os.system("mkdir -p %s" % self.stampdir)
        return "%s ; touch %s" % (txt,self.stampname())
    def test(self):
        return os.path.isfile(self.stampname())
    def cleanup(self):
        os.system("rm -f %s" % self.stampname())

class CompletionGenerator():
    def __init__(self):
        pass
    def next(self,**kwargs):
        return Completion(**kwargs)

class TmpDirCompletionGenerator(CompletionGenerator):
    stamproot = "expire"
    stampdir="."
    def __init__(self,**kwargs):
        self.stamproot = kwargs.pop("stamproot",self.stamproot)
        self.stampdir = kwargs.pop("stampdir",self.stampdir)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed CompletionGenerator args: %s" % str(kwargs))
    def next(self,**kwargs):
        return FileCompletion(stamproot=self.stamproot,stampdir=self.stampdir,**kwargs)

class Task():
    def __init__(self,command,**kwargs):
        self.nodes = None
        self.command = command
        self.completion = kwargs.pop("completion",Completion())
        self.size = kwargs.pop("tasksize",1)
        self.taskid = kwargs.pop("taskid",0)
        if self.taskid!=self.completion.taskid:
            raise LauncherException("Incompatible taskids")
        self.debug = kwargs.pop("debug",0)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed args: %s" % str(kwargs))
        self.has_started = False
    def hasCompleted(self):
        return self.has_started and self.completion.test()
    def startonnodes(self,**kwargs):
        DebugTraceMsg(".. Starting task %d of size %d" % (self.taskid,self.size))
        self.pool = kwargs.pop("pool",None)
        if self.pool is not None and not isinstance(self.pool,(HostLocator)):
            raise LauncherException("Invalid locator object")
        self.commandprefixer = kwargs.pop("commandprefixer",None)
        if self.commandprefixer is None and self.pool is not None \
               and self.pool.pool is not None:
            self.commandprefixer = self.pool.pool.commandprefixer
        if len(kwargs)>0:
            raise LauncherException("Unprocessed Task.startonnodes args: %s" % str(kwargs))
        # wrap with stamp detector
        wrapped = self.completion.attach(self.command)
        # prefix with ssh or ibrun
        if self.commandprefixer is None:
            command = wrapped
        else:
            command = self.commandprefixer(wrapped,self.pool)
        DebugTraceMsg("wrapped and prefixed commandline: "+command,self.debug)
        p = subprocess.Popen(command,shell=True,env=os.environ) # !!! why that os.environ and the env prefix?
        self.has_started = True
        DebugTraceMsg(".. started %d" % self.taskid,self.debug)
    def __repr__(self):
        s = "<< Task %d, commandline: %s, pool size %d" \
            % (self.taskid,self.command,self.size)
        # if not self.nodes==None:
        #     s += ",  running on <%s>" % str(self.nodes)
        s += " >>"
        return s

def testCompletions():
    # trivial case
    task = Task("/bin/true")
    assert(not task.hasCompleted())
    task.startonnodes()
    assert(task.hasCompleted())
    # curent directory
    os.system("rm -f expirefoo5")
    task = Task("/bin/true",taskid=5,
                completion=FileCompletion(taskid=5,stamproot="expirefoo",stampdir=".",))
    print "expected stamp:",task.completion.stampname()
    task.startonnodes()
    time.sleep(1)
    assert(os.path.isfile("./expirefoo5"))
    os.system("rm -f expirefoo5")
    # subdirectory
    os.system("rm -rf launchtest")
    task = Task("/bin/true",taskid=7,
                completion=FileCompletion(taskid=7,
                                          stamproot="expirefoo",stampdir="launchtest",))
    task.startonnodes()
    time.sleep(1)
    assert(os.path.isfile("launchtest/expirefoo7"))
    os.system("rm -rf launchtest")

class RandomSleepTask(Task):
    """for use in many many unit tests"""
    stamproot = "sleepexpire"
    stampdir = "."
    def __init__(self,**kwargs):
        taskid = kwargs.pop("taskid",-1)
        if taskid==-1:
            raise LauncherException("Need an explicit sleep task ID")
        t = kwargs.pop("t",10)
        stamproot = kwargs.pop("stamproot",copy.copy(RandomSleepTask.stamproot))
        stampdir = kwargs.pop("stampdir",copy.copy(RandomSleepTask.stampdir))
        completion = kwargs.pop("completion",None)
        if completion is None:
            completion = FileCompletion\
                (taskid=taskid,stamproot=stamproot,stampdir=stampdir)
        command = SleepCommandGenerator(nmax=1,tmax=t).next()
        Task.__init__(self,command,tasksize=1,taskid=taskid,completion=completion,**kwargs)
        
class TestTasks():
    stampname = "tasktest"
    stampdir = "tasktestdir"
    def setup(self):
        command = "rm -f %s*" % self.stampname
        os.system(command)
        command = "rm -f %s*" % FileCompletion.stamproot
        os.system(command)
        command = "rm -f %s*" % RandomSleepTask.stamproot
        os.system(command)
        command = "rm -rf %s" % self.stampdir
        os.system(command)
    def teardown(self):
        self.setup()
    def testImmediateIssue(self):
        """testImmediateIssue: make sure tasks are run in the background"""
        import time
        ntasks = 10
        start = time.time()
        for i in range(ntasks):
            t = RandomSleepTask(taskid=i,t=6,stamproot=self.stampname)
            t.startonnodes()
        assert(time.time()-start<1)
    def testLeaveStamp(self):
        """testLeaveStamp: make sure tasks leave a stampfile"""
        ntasks = 10; nsleep = 5
        start = time.time()
        for i in range(ntasks):
            t = RandomSleepTask(taskid=i,t=nsleep,stamproot=self.stampname)
            t.startonnodes()
        assert(time.time()-start<1)
        time.sleep(nsleep+1)
        dircontent = os.listdir(".")
        stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
        DebugTraceMsg("stamps: %s" % str(stamps))
        assert(len(stamps)==ntasks)
    def testCompleteOnStamp(self):
        """testCompleteOnStamp: make sure stampfiles are detected"""
        stamproot = "expiresomething"
        ntasks = 10; nsleep = 5
        tasks = []
        start = time.time()
        for i in range(ntasks):
            t = RandomSleepTask(taskid=i,t=nsleep,
                                completion=FileCompletion(stamproot=stamproot,taskid=i))
            t.startonnodes()
            tasks.append(t)
        finished = [ False for i in range(ntasks) ]
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
        assert(len(stamps)==ntasks)
    def testCompleteOnDefaultStamp(self):
        """testCompleteOnDefaultStamp: make sure stampfiles are detected in default setup"""
        ntasks = 10; nsleep = 5
        tasks = []
        start = time.time()
        for i in range(ntasks):
            t = RandomSleepTask(taskid=i,t=nsleep,
                       completion=FileCompletion(stampdir=self.stampdir,taskid=i));
            t.startonnodes(); tasks.append(t)
        stamproot = t.completion.stamproot
        print "stamps based on:",stamproot
        finished = [ False for i in range(ntasks) ]
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
        assert(len(stamps)==ntasks)

#
# different ways of starting up a job
def launcheribrunner(task,line,hosts,poolsize):
    command =  "ibrun -n %d -o %d %s & " % \
              (len(hosts['nodes']),hosts['offset'],line)
    return command
def launcherqsubber(task,line,hosts,poolsize):
    command = "qsub %s" % line
    return command

class Node():
    def __init__(self,host=None,core=None,nodeid=-1):
        self.hostname = host; self.core = core
        self.nodeid = nodeid; self.release()
    def occupyWithTask(self,taskid):
        self.free = False; self.taskid = taskid
    def release(self):
        self.free = True; self.taskid = -1
    def isfree(self):
        return self.free
    def nodestring(self):
        if self.free: return "X"
        else:         return str( self.taskid )

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
    def __init__(self,pool=None,extent=None,offset=None):
        if extent is None or offset is None:
            raise LauncherException("Please specify extent and offset")
        self.pool=pool; self.offset=offset; self.extent=extent
    def __getitem__(self,key):
        return None
    def firsthost(self):
        node = self.pool[self.offset]
        return node.hostname
    def __len__(self):
        return self.extent
    def __str__(self):
        return "Locator: size=%d offset=%d" % (self.extent,self.offset)

class HostPool():
    def __init__(self,**kwargs):
        """Create a list of host dictionaries. Input is either nhosts,
        the number of processes your machine supports,
        or hostlist, a list of host names.
        hostlist items can be `host' or `host;core' """
        hostlist = kwargs.pop("hostlist",None)
        nhosts = kwargs.pop("nhosts",None)
        if hostlist is not None:
            nhosts = len(hostlist)
            self.nodes = []
            for i,h in enumerate(hostlist):
                host = h['host']; core = h['core']
                self.nodes.append( Node(host,core,nodeid=i) )
        elif nhosts is not None:
            hostlist = [ 'localhost' for i in range(nhosts) ]
            self.nodes = [ Node(nodeid=i) for i in range(nhosts) ]
        else: raise LauncherException("HostPool creation needs n or list")
        self.nhosts = nhosts#; self.hostlist = hostlist;
        self.commandprefixer = kwargs.pop("commandprefixer",LocalPrefixer)
        self.debug = kwargs.pop("debug",False)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed HostPool args: %s" % str(kwargs))
    def __getitem__(self,i):
        return self.nodes[i]
    def hosts(self,pool):
        return [ self[i] for i in pool ]
    def unique_hostnames(self,pool=None):
        if pool is None:
            pool = range(len(self))
        u = []
        for h in self.hosts(pool):
            name = h.hostname
            if not name in u:
                u.append(name)
        return sorted(u)
    def requestNodes(self,request):
        """find the starting index of a consecutive free block"""
        start = 0; found = False    
        while not found:
            if start+request>len(self.nodes):
                return None
            for i in range(start,start+request):
                found = self[i].isfree()
                if not found:
                    start = i+1; break
        if found:
            return HostLocator(self,offset=start,extent=request)
        else: return None
    def occupyNodes(self,locator,taskid):
        for n in range(locator.offset,locator.offset+locator.extent):
            self[n].occupyWithTask(taskid)
    def releaseNodesByTask(self,taskid):
        for n in self.nodes:
            if n.taskid==taskid:
                DebugTraceMsg("releasing %s, core %s"
                              % (str(n.hostname),str(n.core)),
                              self.debug)
                n.release()
    def __repr__(self):
        return str ([ "%d,:%s" % (n.i,n.nodestring())
                      for n in self.nodes ]
                    )
    def __len__(self):
        return self.nhosts

def testHostPoolN():
    p = HostPool(nhosts=5)
    # request a 3 node pool
    pool = p.hosts([1,3])
    assert(len(pool)==2)
    assert(pool[0].nodeid==1 and pool[1].nodeid==3)
    p1 = p.requestNodes(3)
    assert(len(p1)==3)
    task = 27
    p.occupyNodes(p1,task)
    # it is not possible to get 4 more nodes
    p2 = p.requestNodes(4)
    assert(p2 is None)
    # see if the status is correctly rendered
    assert(not p[0].free and p[3].free)
    assert(p[0].nodestring()==str(task) and p[3].nodestring()=="X")
    # after we release used pool, we can request more
    p.releaseNodesByTask(task)
    p2 = p.requestNodes(4)
    assert(len(p2)==4)
    

class HostList():
    def __init__(self,list=[],tag=""):
        self.hostlist = []; self.tag = tag; self.uniquehosts = []
        for h in list:
            self.append(h)
    def append(self,h,c=0):
        if not re.search(self.tag,h):
            h = h+self.tag
        if h not in self.uniquehosts:
            self.uniquehosts.append(h)
        self.hostlist.append( {'host':h, 'core':c} ) #"%s;%s" % (h,str(c)))
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

def HostName():
    return os.environ["HOSTNAME"].split(".")[1]
def JobId():
    hostname = HostName()
    if hostname=="ls4":
        return os.environ["JOB_ID"]
    elif hostname=="stampede":
        return os.environ["SLURM_JOB_ID"]
    else:
        raise LauncherException("Unknown host <%s>" % hostname)

def TACCHostList(**kwargs):
    hostname = HostName()
    if hostname=="ls4":
        return SGEHostList(tag=".ls4.tacc.utexas.edu",**kwargs)
    elif hostname=="stampede":
        return SLURMHostList(tag=".stampede.tacc.utexas.edu",**kwargs)
    else:
        raise LauncherException("Unknown host <%s>" % hostname)
        
def testTACChostlist():
    for h in TACCHostList():
        print "hostfile line:",h
        assert( 'core' in h and 'host' in h )
        host = h["host"].split(".")
        assert( len(host)>1 and host[1]==HostName() )

class TACCHostPool(HostPool):
    def __init__(self):
        HostPool.__init__( self, hostlist=TACCHostList(),
                           commandprefixer=SSHPrefixer )

def testPEhostpools():
    hostname = HostName()
    pool = TACCHostPool()
    if hostname=="stampede":
        assert(len(pool)%16==0)
    elif hostname=="ls4":
        assert(len(pool)%12==0)
    else:
        assert(False)

class LocalHostPool(HostPool):
    def __init__(self):
        HostPool.__init__(self,['localhost'], commandprefixer=LocalPrefixer)

class TaskQueue():
    launcherdir = "."
    def __init__(self,**kwargs):
        self.queue = []; self.running = []; self.completed = []
        self.maxsimul = 0; self.submitdelay = 0
        self.debug = kwargs.pop("debug",0)
#         launcherdir = kwargs.pop("launcherdir",copy.copy(TaskQueue.launcherdir))
#         if launcherdir!=".":
#             self.launcherdir = os.getcwd()+"/"+launcherdir
#             self.rm_launcherdir()
#             os.mkdir(self.launcherdir)
        if len(kwargs)>0:
            raise LauncherException("Unprocessed TaskQueue args: %s" % str(kwargs))
    def isEmpty(self):
        return self.queue==[] and self.running==[]
    def enqueue(self,task):
        task.launcherdir = self.launcherdir
        self.queue.append(task)
    def startQueued(self,hostpool):
        """for all queued, try to find nodes to run it on;
        the hostpool argument is a HostPool object"""
        tqueue = copy.copy(self.queue)
        for t in tqueue:
            locator = hostpool.requestNodes(t.size)
            if locator is None: continue
            if self.submitdelay>0:
                time.sleep(self.submitdelay)
            if self.debug>0:
                print "Starting task <%s> on locator <%s>" % (str(t),str(locator))
            t.startonnodes(pool=locator)
            hostpool.occupyNodes(locator,t.taskid)
            self.queue.remove(t)
            self.running.append(t)
            self.maxsimul = max(self.maxsimul,len(self.running))
    def findCompleted(self):
        for t in self.running:
            if t.hasCompleted():
                self.running.remove(t)
                self.completed.append(t)
                DebugTraceMsg(".. job completed: %d" % t.taskid)
                return t.taskid
        return None
    def __repr__(self):
        return "completed: "+str([ t.taskid for t in sorted(self.completed)])+";"+\
               "\nqueued: "+str([ t.taskid for t in self.queue])+";"+\
               "\nrunning: "+str([ t.taskid for t in sorted(self.running)])+"."
    def savestate(self):
        f = open("queuestate","w")
        f.write("queued\n")
        for t in self.queue:
            f.write(t.command+"\n")
        f.write("running\n")
        for t in self.running:
            f.write(t.command+"\n")
        f.write("completed\n")
        for t in self.completed:
            f.write(t.command+"\n")
        f.close()

def testTaskQueue():
    """testTaskQueue: queue and detect a task in a queue
    using the default task prefixer and completion tester"""
    pool = HostPool(nhosts=5)
    queue = TaskQueue()
    nsleep = 5; t_id = 13
    task = RandomSleepTask(taskid=t_id,t=nsleep)
    queue.enqueue(task)
    queue.startQueued(pool)
    assert(task in queue.running)
    time.sleep(nsleep)
    complete_id = queue.findCompleted()
    print "found completed:",complete_id
    assert(complete_id==t_id)
    task.completion.cleanup()
    assert(True)

def testTaskQueueWithLauncherdir():
    """testTaskQueueWithLauncherdir: same, but test correct use of launcherdir"""
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
    complete_id = queue.findCompleted()
    print "completed:",complete_id
    assert(complete_id==t_id)
    files = os.listdir(dirname)#queue.launcherdir)
    print files
    assert(len(files)==1)
    os.system("/bin/rm -rf %s" % dirname)
    assert(True)

class TaskGenerator():
    """iterator class that can yield the following:
    a Task instance, or the keyword `stall'"""
    def __init__(self,commandlinegenerator,**kwargs):
        self.commandlinegenerator = commandlinegenerator
        self.taskcount = 0
        self.debug = kwargs.pop("debug",False)
        self.completion = kwargs.pop("completion",CompletionGenerator())
        if not isinstance(self.completion,(CompletionGenerator)):
            raise LauncherException("TaskGenerator completion should be completion generator")
        if len(kwargs)>0:
            raise LauncherException("Unprocessed TaskGenerator args: %s" % str(kwargs))
    def next(self):
        command,tasksize = self.commandlinegenerator.next()
        DebugTraceMsg("next commandline <%s>" % command,self.debug)
        if command=="stall":
            return command
        elif command=="stop":
            raise StopIteration
        else:
            taskid = self.taskcount
            self.taskcount += 1
            return Task(command,tasksize=tasksize,taskid=taskid,
                        completion=self.completion.next(taskid=taskid))
    def __iter__(self): return self

class TestTaskGenerators():
    def countedcommand(self):
        count = self.icommand; self.icommand += 1
        return "/bin/true command%d\n" % count
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
            commandlines.write(self.countedcommand())
        commandlines.close()
    def teardown(self):
        os.system("rm -rf %s %s" % (self.fn,self.dir))
    def testFileTaskGenerator(self):
        """testFileTaskGenerator: test that the taskgenerator can deal with a file"""
        count = 0
        for t in TaskGenerator( FileCommandlineGenerator(self.fn,1) ):
            count += 1
        print self.ncommand
        assert(count==self.ncommand)
    def testFileTaskGeneratorNext(self):
        """testFileTaskGeneratorNext: file task generator, but using a while/next loop"""
        count = 0; generator = TaskGenerator( FileCommandlineGenerator(self.fn,1) )
        starttime = time.time()
        while True:
            try:
                t = generator.next(); count += 1
            except:
                break
            if time.time()-starttime>3:
                print "this is taking too long"
                assert(False)
        print self.ncommand
        assert(count==self.ncommand)
    def testDynamicTaskGeneratorMax(self):
        """testDynamicTaskGeneratorMax: generate tasks until max"""
        nmax = 50
        generator = TaskGenerator( DynamicCommandlineGenerator(nmax=nmax) )
        for count,command in enumerate(generator):
            generator.commandlinegenerator.append(self.countedcommand())
        print count
        assert(count==nmax)
    def testDynamicTaskGeneratorLong(self):
        """testDynamicTaskGeneratorInf: generate tasks until dynamic finish"""
        nmax = self.ncommand+10
        generator = TaskGenerator( DynamicCommandlineGenerator() )
        count = 0
        for t in enumerate(generator):
            count += 1
            generator.commandlinegenerator.append(self.countedcommand())
            if count==nmax:
                generator.commandlinegenerator.finish()
        print count
        assert(count==nmax)
    def testDynamicTaskGeneratorShort(self):
        """testDynamicTaskGeneratorInf: generate tasks until dynamic finish"""
        nmax = self.ncommand-10
        generator = TaskGenerator( DynamicCommandlineGenerator() )
        count = 0
        for t in enumerate(generator):
            count += 1
            generator.commandlinegenerator.append(self.countedcommand())
            if count==nmax:
                generator.commandlinegenerator.finish()
        print count
        assert(count==nmax)
    def ttestTaskGeneratorTmpDir(self):
        nmax = self.ncommand; pool = HostPool(nhosts=nmax)
        count = 0
        for t in TaskGenerator( FileCommandlineGenerator(self.fn,1),
              completion=TmpDirCompletionGenerator(stampdir=self.dir) ):
            locator = pool.requestNodes(1)
            if locator is None:
                raise LauncherException("there should be space")
            t.startonnodes(locator)
        files = os.listdir(self.dir); print files
        assert(len(files)==nmax)

class ModuloCommandlineGenerator(FileCommandlineGenerator):
    modulocount = 0
    def __init__(self,filename,modulo):
        embedded = FileCommandlineGenerator(filename)
        mastername = filename+".master"
        master = open(mastername,"w")
        count = 0; modfile = None
        while True:
            if modfile is None:
                modname = filename+"."+str(mod(count,modulo))
                modfile = open(modname)
            try:
                line = embedded.next(); end = False
            except StopIteration:
                end = True
            modfile.write(line+"\n")
            if end or mod(count,modulo)==0:
                master.write("./%s\n" % modname)
                modfile.close(); modfile = None
            if end: 
                master.close(); break
        FileCommandlineGenerator.__init__(self,mastername)

def testModuleCommandline():
    ntasks = 40; fn = "modtest"
    MakeRandomSleepFile(fn,ntasks)
    os.system("/bin/rm -f %s" % fn)
    assert(True)


####
#### Launcher Job class:
#### jobs take only one processor; 
#### we do everything for the user except
#### making the host list
####

        
def launchercommandwrap(task,line):
    id = task.id
    stamp = task.job.launcherdir+"/"+defaultExpireStamp(id)
    xfile = task.job.launcherdir+"/exec"+str(id)
    x = open(xfile,"w")
    x.write("#!/bin/bash\n\n")
    x.write(line+" # the actual command\n")
    #x.write("echo \"expiring "+str(id)+"\" # just a trace message\n")
    x.write("touch "+stamp+" # let the event loop know that the job is finished\n")
    x.close(); os.chmod(xfile,stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
    return xfile
def launcherqsubwrap(task,line):
    id = task.id
    stamp = task.job.launcherdir+"/"+defaultExpireStamp(id)
    xfile = task.job.launcherdir+"/exec"+str(id)
    x = open(xfile,"w")
    x.write("""#!/bin/bash

#$   -q development
#$   -V
#$   -cwd
#$   -pe 1way 12
#$   -l h_rt=0:20:00
#$   -N launchtest
#$   -j y
#$   -o $JOB_NAME.oe$JOB_ID
## #$   -M yournamehere@tacc.utexas.edu
## #$   -m e
#$ -A A-ccsc

ibrun """+line+"\n")
    x.write("echo \"expiring "+str(id)+"\" # just a trace message\n")
    x.write("touch "+stamp+" # let the event loop know that the job is finished\n")
    x.close()
    #print "Creating file <%s> for executing <%s>" % (xfile,line)
    return xfile
# this is executed by a Job
def launcherCompletionTestPrep(job):
    star = job.launcherdir+"/"+defaultExpireStamproot()+"*"
    job.stamps = glob.glob(star)
# this is executed by a Task
def launcherCompletionTest(task):
    q = task.job.launcherdir+"/"+defaultExpireStamp(task.id)
    r = q in task.job.stamps
    return r

def LocalPrefixer(command,pool):
    return command

def SSHPrefixer(command,pool):
    env = "env" ; pwd = "" ; numa = ""
    #if core is not None: numa = "numactl --physcpubind=%s" % core
    for e in os.environ:
        val = os.environ[e]
        #val = re.sub('\(','\(',val); val = re.sub('\)','\)',val)
        if e=="PWD" : pwd = val
        if not re.search("[; ()]",val):
            env += " %s=\"%s\"" % (e,val)
    #return "ssh %s \"cd %s ; %s %s %s &\"" % (host,pwd,env,numa,line)
    return "ssh %s 'cd %s ; %s %s %s' " % (pool.firsthost(),pwd,env,numa,command)

class testPrefixTaskToSelf():
    hostname = HostName()
    stampname = "prefixtasktest"
    def setup(self):
        command = "rm -f %s*" % self.stampname
        os.system(command)
        command = "rm -f %s*" % FileCompletion.stamproot
        os.system(command)
        command = "rm -f %s*" % RandomSleepTask.stamproot
        os.system(command)
    def teardown(self):
        self.setup()
    def testRemoteSSH(self):
        hosts = TACCHostPool().unique_hostnames(); print hosts
        if len(hosts)>1:
            pool = HostPool(hostlist=HostList([hosts[1]]))
            fn = "testremotessh"; pwd = os.getcwd()
            t = Task("hostname > %s" % fn)
            t.startonnodes(pool=HostLocator(pool=pool,extent=1,offset=0),
                           commandprefixer=SSHPrefixer)
            time.sleep(1)
            command = "cat %s/%s" % (pwd,fn)
            p = subprocess.Popen(command,shell=True,stdout=subprocess.PIPE)
            hostread = p.communicate()[0].strip(); print hostread
            assert(hostread==hosts[1])
            os.system("/bin/rm -f %s" % fn)
        else: assert(True)
    def testLocalImmediateIssue(self):
        """testSSHImmediateIssue: make sure ssh tasks are run in the background"""
        import time
        start = time.time()
        t = RandomSleepTask(taskid=1,t=6,stamproot=self.stampname)
        t.startonnodes(pool=HostLocator(pool=HostPool(nhosts=1,commandprefixer=LocalPrefixer),
                                        extent=1,offset=0)
                       )
        elapsed = time.time()-start
        print "elapsed time for a local issue",elapsed
        assert(elapsed<1)
    def testSSHImmediateIssue(self):
        """testSSHImmediateIssue: make sure ssh tasks are run in the background"""
        import time
        start = time.time()
        t = RandomSleepTask(taskid=1,t=6,stamproot=self.stampname)
        t.startonnodes(pool=HostLocator(pool=TACCHostPool(),extent=1,offset=0),
                       commandprefixer=SSHPrefixer)
        elapsed = time.time()-start
        print "elapsed time for an ssh",elapsed
        assert(elapsed<1)
    def testSSHLeaveStamp(self):
        """testSSHLeaveStamp: leave a single stampfile"""
        nsleep = 4; taskid = 17
        taccpool = TACCHostPool()
        start = time.time()
        t = RandomSleepTask(taskid=taskid,t=nsleep,stamproot=self.stampname,debug=0)
        nodepool = taccpool.requestNodes(1) #HostLocator(pool=taccpool)
        if nodepool is None:
            assert(False) # there should be enough nodes open
        print "available pool:",str(nodepool)
        assert(nodepool.offset==0)
        t.startonnodes(pool=nodepool,commandprefixer=SSHPrefixer)
        taccpool.occupyNodes(nodepool,t.taskid)
        time.sleep(nsleep+1)
        dir = t.completion.stampdir; dircontent = os.listdir(dir)
        print "looking for stamps and found:",sorted(dircontent)
        stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
        print "stamps:",sorted(stamps)
        assert(self.stampname+str(taskid) in stamps)
    def testSSHLeaveStampLoop(self):
        """testSSHLeaveStampLoop: make sure tasks leave a stampfile"""
        ntasks = 7; nsleep = 5
        taccpool = TACCHostPool()
        assert(ntasks<len(taccpool)) # just to make sure we can run this
        start = time.time()
        for itask in range(ntasks):
            t = RandomSleepTask(taskid=itask,t=nsleep,stamproot=self.stampname,debug=0)
            nodepool = taccpool.requestNodes(1) #HostLocator(pool=taccpool)
            if nodepool is None:
                assert(False) # there should be enough nodes open
            print "available pool:",str(nodepool)
            assert(nodepool.offset==itask)
            t.startonnodes(pool=nodepool,commandprefixer=SSHPrefixer)
            taccpool.occupyNodes(nodepool,t.taskid)
        assert(time.time()-start<1)
        time.sleep(nsleep+1)
        dir = t.completion.stampdir; dircontent = os.listdir(dir)
        print "looking for stamps and found:",sorted(dircontent)
        stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
        print "stamps:",sorted(stamps)
        assert(len(stamps)==ntasks)

class LauncherJob():
    """LauncherJob class. Keyword arguments:
    hostpool : a HostPool instance (required)
    taskgenerator : a TaskGenerator instance (required)
    launcherdir or jobid : dir for tmps, or id to attach to standard dir name
    delay : between task checks
    debug : list of keywords (queue+job)
    """
    def __init__(self,**kwargs):
        self.hostpool = kwargs.pop("hostpool",None)
        if self.hostpool is None:
            raise LauncherException("Need a host pool")
        self.taskgenerator = kwargs.pop("taskgenerator",None)
        if self.taskgenerator is None:
            raise LauncherException("Need a task generator")
        self.jobid = kwargs.pop("jobid",0)
        #self.launcherdir = kwargs.pop("launcherdir","pylauncher_tmpdir"+str(self.jobid))
        self.delay = kwargs.pop("delay",.5)
        debugs = kwargs.pop("debug","")
        queuedebug = re.search("queue",debugs)
        self.queue = TaskQueue()#(launcherdir=self.launcherdir)
        self.maxruntime = kwargs.pop("maxruntime",0)
        self.debug = re.search("job",debugs)
        self.completed = 0; self.tock = 0        
        if len(kwargs)>0:
            raise LauncherException("Unprocessed LauncherJob args: %s" % str(kwargs))
    def tick(self):
        DebugTraceMsg("\ntick %d\nQueue:\n%s" % (self.tock,str(self.queue)),self.debug)
        self.tock += 1
        self.queue.startQueued(self.hostpool)
        completeID = self.queue.findCompleted()
        if not completeID is None:
            DebugTraceMsg("completed: %d" % completeID,self.debug)
            self.completed += 1
            self.hostpool.releaseNodesByTask(completeID)
            message = "expired %s" % str(completeID)
        else:
            try:
                task = self.taskgenerator.next()
                if task=="stall":
                    message = "stalling"
                else:
                    if not isinstance(task,(Task)):
                        raise LauncherException("Not a task: %s" % str(task))
                    DebugTraceMsg("enqueueing new task <%s>" % str(task),self.debug)
                    self.queue.enqueue(task)
                    message = "continuing"
            except:
                if self.queue.isEmpty():
                    message = "finished"
                else:
                    message = "continuing"
            time.sleep(self.delay)
        DebugTraceMsg("status: %s" % message,self.debug)
        return message
    def run(self):
        starttime = time.time()
        while True:
            res = self.tick()
            if res=="finished":
                break
            if self.maxruntime>0 and time.time()-starttime>self.maxruntime:
                break

class TestLauncherJobs():
    def removecommandfile(self):
        os.system("rm -f %s" % self.fn)
    def setup(self):
        self.makecommandfile()
    def makecommandfile(self):
        """make a commandlines file"""
        self.fn = "unittestlines"; self.ncommand = 6; self.maxsleep = 4
        MakeRandomSleepFile( self.fn,self.ncommand,tmax=self.maxsleep )
        self.icommand = 0; 
    def teardown(self):
        self.removecommandfile()
    def testLocalFileTaskJob(self):
        ntasks = self.ncommand
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,1) ),
            hostpool=HostPool( nhosts=ntasks ),
            delay=.2,
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
                raise LauncherException(estr)
        assert(True)
    def testLocalFileTaskJobCustom(self):
        launcherdir = "testlauncherjobs.tmp"
        ntasks = self.ncommand
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,1),
                      completion=TmpDirCompletionGenerator(stampdir=launcherdir) ),
            hostpool=HostPool( nhosts=ntasks ), #launcherdir=launcherdir,
            debug="queue,job"
            )
        starttime = time.time()
        while True:
            res = job.tick()
            assert( os.path.isdir(launcherdir) )
            elapsed = time.time()-starttime
            print "tick:",job.tock,"elapsed: %5.3e" % elapsed,"result:",res
            if res=="finished": break
            elif re.match("^expire",res):
                print res
            if elapsed>2+ntasks*job.delay+self.maxsleep:
                estr = "This is taking too long: %d sec for %d tasks" % (int(elapsed),ntasks)
                print estr
                raise LauncherException(estr)
        os.system( "/bin/rm -rf %s" % launcherdir )
        assert(True)
    def testSSHFileTaskJob(self):
        ntasks = self.ncommand
        hostpool = TACCHostPool()
        assert( ntasks<=len(hostpool) ) # make sure we can run without delay
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,1) ),
            hostpool=hostpool,
            delay=.2,
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
    def testLauncherJobRun(self):
        ntasks = self.ncommand; delay = .2
        hostpool = TACCHostPool()
        assert( ntasks<=len(hostpool) ) # make sure we can run without delay
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,1) ),
            hostpool=hostpool,
            delay=delay,maxruntime=self.maxsleep+ntasks*delay+2,
            debug="queue,job"
            )
        job.run()
        assert(True)
    def testLauncherJobRunWithWait(self):
        hostpool = TACCHostPool()
        self.ncommand = 2*len(hostpool)
        self.removecommandfile(); self.makecommandfile()
        ntasks = self.ncommand; delay = .2
        job = LauncherJob( 
            taskgenerator=TaskGenerator( FileCommandlineGenerator(self.fn,1) ),
            hostpool=hostpool,
            delay=delay,maxruntime=2*self.maxsleep+ntasks*delay+2,
            debug="queue,job"
            )
        job.run()
        assert(True)

def ClassicLauncher(commandfile,**kwargs):
    debug = kwargs.pop("debug","")
    hostdebug = re.search("host",debug)
    jobdebug = re.search("job",debug)
    queuebug = re.search("queue",debug)
    taskdebug = re.search("task",debug)
    cores = kwargs.pop("cores",1)
    jobid = JobId()
    job = LauncherJob(
        hostpool=HostPool(hostlist=TACCHostList(),debug=hostdebug),
        taskgenerator=TaskGenerator( FileCommandlineGenerator(commandfile,cores),
            completion=TmpDirCompletionGenerator
                           (stamproot="expire",stampdir="pylauncher_tmp"+str(jobid)),
            debug=taskdebug ),
        debug=debug,**kwargs)
    job.run()

if __name__=="__main__":
    hostlist = SLURMgetpehosts()
    print hostlist
