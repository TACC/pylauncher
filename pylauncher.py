"""pylauncher.py version 1.5 2012/10/09

A python based launcher utility for packaging sequential or
low parallel jobs in one big parallel job

Author: Victor Eijkhout
eijkhout@tacc.utexas.edu

Change log
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
import subprocess
import sys
import time

class LauncherException(Exception):
    """A very basic exception mechanism"""
    def __init__(self,str):
        self.str = str
        def __str__(self):
            return self.str
                                
class Task():
    def __init__(self,command,tasksize,id):
        self.size = tasksize
        self.nodes = None
        self.command = command; self.id = id
    def setJob(self,job):
        self.job = job
        self.expireStamp = job.launcherdir+"/"+defaultExpireStamp(self.id)
    def hasCompleted(self):
        return self.job.completionTest(self)
    def startonnodes(self,pool):
        print ".. Starting task",self.id,"of size",self.size
        self.nodes = pool['nodes']
        #print ".. node startup:",self.command,"on",pool
        wrapped = self.commandwrap(self.command)
        command = self.commandprefixer(wrapped,pool,self.size)
        p = subprocess.Popen(command,shell=True,env=os.environ)
#        p.wait()
#        r = p.returncode
#         r = os.system(command)
#         while r!=0:
#             time.sleep(30)
#             print ".. startup of %d failed with return %d; retrying" % \
#                   (self.id,r)
#             r = os.system(command)
        print ".. started %d" % self.id
    def __repr__(self):
        s = "<< Task %d, commandline: %s, pool size %d" \
            % (self.id,self.command,self.size)
        if not self.nodes==None:
            s += ",  running on <%s>" % str(self.nodes)
        s += " >>"
        return s

####
#### General Job class:
#### the user has to write all the functions
#### for job wrapping, starting, and testing 
#### whether a job has ended
####
def nowrap(txt):
    return txt
def nowraptwo(task,txt,p,n):
    return txt
def istrue(s,i):
    return True
class Job():
    class TaskQueue():
        def __init__(self):
            self.queue = []; self.running = []; self.completed = []
            self.maxsimul = 0; self.submitdelay = 0
        def isEmpty(self):
            return self.queue==[] and self.running==[]
        def startQueued(self,nodes):
            tqueue = copy.copy(self.queue)
            for t in tqueue:
                pool = nodes.requestNodes(t.size)
                if pool is not None:
                    if self.submitdelay>0:
                        time.sleep(self.submitdelay)
                    t.startonnodes(
                        {'nodes':nodes.hosts(pool),'offset':pool[0]})
                    nodes.occupyNodes(pool,t.id)
                    self.queue.remove(t)
                    self.running.append(t)
                    self.maxsimul = max(self.maxsimul,len(self.running))
        def enqueue(self,task):
            self.queue.append(task)
        def findCompleted(self):
            for t in self.running:
                if t.hasCompleted():
                    self.running.remove(t)
                    self.completed.append(t)
                    print ".. job completed:",t.id
                    return t.id
            return None
        def __repr__(self):
            return "completed: "+str([ t.id for t in self.completed])+";"+\
                   "\nqueued: "+str([ t.id for t in self.queue])+";"+\
                   "\nrunning: "+str([ t.id for t in self.running])+"."
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
    class HostPool():
        def __init__(self,nhosts=None,hostlist=None):
            """Create a list of host dictionaries. Input is either nhosts,
            the number of processes your machine supports,
            or hostlist, a list of host names.
            hostlist items can be `host' or `host;core' """
            if hostlist is not None:
                nhosts = len(hostlist)
                self.nodes = [ {'free':True,'task':-1}
                               for i in range(nhosts) ]
                i=0
                for h in hostlist:
                    hh = h.split(';')
                    if len(hh)==2:
                        host = hh[0]; core = hh[1]
                    else:
                        host = hh; core = None
                    self.nodes[i]['host'] = host; self.nodes[i]['core'] = core
                    i+=1
            elif nhosts is not None:
                self.nodes = [ {'free':True,'task':-1,'host':None,'core':None}
                               for i in range(nhosts) ]
            else: raise LauncherException("HostPool creation needs n or list")
            self.nhosts = nhosts
        def hosts(self,pool):
            return [ self.nodes[i] for i in pool ]
        def requestNodes(self,n):
            start = 0; found = False    
            while not found:
                if start+n>self.nhosts:
                    return None
                for i in range(start,start+n):
                    found = self.nodes[i]['free']
                    if not found:
                        start = i+1; break
            if found:
                return range(start,start+n)
            else: return None
        def occupyNodes(self,pool,id):
            for n in pool:
                self.nodes[n]['free'] = False
                self.nodes[n]['task'] = id
        def releaseNodes(self,id):
            for n in self.nodes:
                if n['task']==id:
                    print "releasing %s, core %s" % (n['host'],n['core'])
                    n['free'] = True
        def nodestring(self,i):
            if self.nodes[i]['free']:
                return "X"
            else: return self.nodes[i]['task']
        def __repr__(self):
            return str ([ "%d,:%s" % (i,self.nodestring(i))
                          for i in range(self.nhosts) ]
                        )
        def __len__(self):
            return self.nhosts
    def __init__(self,nhosts=1,launcherdir="pylauncher_tmpdir",
                 commandgenerator=None,commandobject=None,
                 commandwrap=nowrap,commandprefixer=nowraptwo,
                 hostlist=None,delay=1.,
                 **kwargs):
        self.launcherdir = launcherdir
        os.system("rm -rf %s ; mkdir %s" % (launcherdir,launcherdir) )
        self.nodes = self.HostPool(nhosts,hostlist)
        print "Starting job on %d hosts" % self.nodes.nhosts
        self.taskid = 0
        self.tasks = self.TaskQueue();
        self.maxsimul = 0; self.completed = 0
        self.queueExhausted = False
        self.ticks = 0; self.delay = delay
        self.debug = kwargs.pop("debug",0)
        if commandgenerator is not None:
            self.commandgenerator = commandgenerator()
        else: self.commandgenerator = None
        self.completionTest = \
            kwargs.pop("completionTest",defaultCompletionTest)
        self.completionTestPrep = \
            kwargs.pop("completionTestPrep",defaultCompletionTestPrep)
        self.commandobject = commandobject
        Task.commandwrap = commandwrap
        Task.commandprefixer = commandprefixer
        #Task.completionTest = completionTest
        #Task.completionTestPrep = completionTestPrep
    def newtask(self):
        if self.commandgenerator is not None:
            self.nexttask = self.commandgenerator.next()
        elif self.commandobject is not None:
            self.nexttask = self.commandobject.generate()
        else:
            print "ERROR can not generate next task"; sys.exit(1)
        r = self.nexttask; # print r
        newcommand,tasksize = r
        if newcommand=="stop":
            self.queueExhausted = True
            return None
        elif newcommand=="stall":
            return None
        self.taskid += 1
        commandline = newcommand
        task = Task(commandline,tasksize,self.taskid)
        return task
    def tick(self):
        time.sleep(self.delay)
        self.ticks += 1; self.tasks.savestate()
        # if self.ticks==self.crashtick: return "finished"
        if self.debug>0:
            print "\nt=",self.ticks,"\n",self.tasks,"\n",self.nodes
        if self.queueExhausted and self.tasks.isEmpty():
            if self.debug>0:
                print "\n====\nJob completed:\n#tasks = %d\n#hosts = %d\n" % \
                      (self.completed,len(self.nodes))
            return "finished"
        self.tasks.startQueued(self.nodes)
        if self.completionTestPrep is not None:
            self.completionTestPrep(self)
        completeID = self.tasks.findCompleted()
        if not completeID is None:
            self.completed += 1
            self.nodes.releaseNodes(completeID)
            if self.commandobject is not None:
                self.commandobject.expire(completeID)
            return "expired "+str(completeID)
        if not self.queueExhausted:
            while True:
                newrequest = self.newtask() # make new job and enqueue it
                if newrequest is  None: break
                newrequest.setJob(self)
                self.tasks.enqueue(newrequest)
        return None

####
#### Launcher Job class:
#### jobs take only one processor; 
#### we do everything for the user except
#### making the host list
####

# cough up commandlines
def launchercommandgenerator(file,cores):
    for line in file.readlines():
        if re.match('^ *#',line) or re.match('^ *$',line):
            continue # skip blank and comment
        if cores=="file":
            c,l = line.strip().split(",",1); c = int(c)
        else:
            l = line.strip(); c = cores
        yield l,c
    yield "stop",0

# tools to recognize when a job has ended
def defaultExpireStamproot():
    return "expire"
def defaultExpireStamp(id):
    return defaultExpireStamproot()+str(id)
def defaultCompletionTestPrep(job):
    return
def defaultCompletionTest(task):
    file = task.expireStamp
    return os.path.isfile(file)
        
def launchercommandwrap(task,line):
    id = task.id
    stamp = task.job.launcherdir+"/"+defaultExpireStamp(id)
    xfile = task.job.launcherdir+"/exec"+str(id)
    x = open(xfile,"w")
    x.write("#!/bin/bash\n\n")
    x.write(line+" # the actual command\n")
    x.write("echo \"expiring "+str(id)+"\" # just a trace message\n")
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
## #$   -M eijkhout@tacc.utexas.edu
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

#
# different ways of starting up a job
def launcherssher(task,line,hosts,poolsize):
    """for an ssh'ing launcher we use the first host"""
    h = hosts['nodes'][0]; host = h['host']; core = h['core']
    print "launch on host %s, core %s" % (host,str(core))
    env = "" ; pwd = "" ; numa = ""
    if core is not None: numa = "numactl --physcpubind=%s" % core
    for e in os.environ:
        if e=="PWD" : pwd = os.environ[e]
        if not re.search("[; ]",os.environ[e]):
            env += "%s=\"%s\" " % (e,os.environ[e])
    return "ssh %s \"cd %s ; env %s %s %s &\"" % \
           (host,pwd,env,numa,line)
def launcheribrunner(task,line,hosts,poolsize):
    command =  "ibrun -n %d -o %d %s & " % \
              (len(hosts['nodes']),hosts['offset'],line)
    return command
def launcherqsubber(task,line,hosts,poolsize):
    command = "qsub %s" % line
    return command

####
#### TACC Launcher Job class:
#### we use the PE_HOSTFILE to dig up the host list.
####

class LauncherJob(Job):
    def __init__(self,**kwargs):
        hostlist = kwargs.pop("hostlist",launchergetpehosts())
        launcherdir = kwargs.pop\
             ("launcherdir",
              os.getcwd()+"/"+"pylauncher_tmpdir."+os.getenv("JOB_ID"))
        commandfile = kwargs.pop("commandfile",None)
        commandprefixer = kwargs.pop("commandprefixer",launcherssher)
        defaultcores = kwargs.pop("cores",1)
        commandgenerator = kwargs.pop("commandgenerator",None)
        commandobject = kwargs.pop("commandobject",None)
        if commandgenerator is None and commandobject is None:
            if commandfile is None:
                print "Error: needs commandfile or commandgenerator"
                sys.exit(1)
            else:
                inhandle = open(commandfile)
                commandgenerator= lambda : launchercommandgenerator(inhandle,defaultcores)
        Job.__init__(self,
                     launcherdir=launcherdir,
                     commandgenerator=commandgenerator,
                     commandobject=commandobject,
                     commandwrap=launchercommandwrap,
                     completionTest=launcherCompletionTest,
                     completionTestPrep=launcherCompletionTestPrep,
                     commandprefixer=commandprefixer,
                     hostlist=hostlist,
                     **kwargs)

def launchergetpehosts():
    """Parse the $PE_HOSTFILE and make a hostlist;
    hosts with multiplicity turn into host;0 host;1 ..."""
    hostfile = os.environ["PE_HOSTFILE"]
    hostfile = open(hostfile,"r")
    hostlist = []
    for h in hostfile.readlines():
        line = h.strip(); line = line.split(); host = line[0]; n = line[1]
        for i in range(int(n)):
            hostlist.append(host+";"+str(i))
    return hostlist

class TACCDynamicLauncherJob(LauncherJob):
    def __init__(self,**kwargs):
        hostlist = kwargs.pop("hostlist",launchergetpehosts())
        LauncherJob.__init__(self,hostlist=hostlist,
                             **kwargs)

def ClassicLauncher(commandfile,cores=1):
    job = LauncherJob(commandfile=commandfile,cores=cores)
    while True:
        state = job.tick() # delay, recognize expiries, start new jobs
        if state is not None and re.match('^finished',state):
            break

def CoreLauncher(commandfile):
    job = LauncherJob(commandfile=commandfile,cores="file")
    while True:
        state = job.tick() # delay, recognize expiries, start new jobs
        if state is not None and re.match('^finished',state):
            break

def DynamicLauncher(generator):
    job = LauncherJob(commandobject=generator)
    while True:
        state = job.tick() # delay, recognize expiries, start new jobs
        if state is not None and re.match('^finished',state):
            break

def MPILauncher(commandfile,**kwargs):
    job = LauncherJob(commandfile=commandfile,
                      commandprefixer=launcheribrunner,
                      cores="file",**kwargs)
    while True:
        state = job.tick() # delay, recognize expiries, start new jobs
        if state is not None and re.match('^finished',state):
            break
