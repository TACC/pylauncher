def testCountedCommandGenerator():
    ntasks = 15
    generator = CountedCommandGenerator(nmax=ntasks)
    count = 0
    for g in generator:
        assert( re.match('echo',g) )
        count += 1
    assert(count==ntasks)

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
        gs = g.split(); print(gs,flush=True)
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
            print("counted barrier %d after %d lines" % (count_barrier,count),flush=True)
            assert(count_barrier<=nbarrier)
            continue
        gs = g.split(); print(gs,flush=True)
        # echo i 2>&1 > /dev/null ; sleep t
        # 0    1 2    3 4         5 6     7
        assert( int(gs[1])==count and int(gs[7])<=tmax )
        count += 1
    print("tasks:",count,flush=True)
    assert(count==ntasks)
    print("barriers:",count_barrier,flush=True)
    assert(count_barrier==nbarrier)

def testGeneratorList():
    """testGeneratorList: Generate commands from a list and count them"""
    clist = [ Commandline("foo",cores=2), Commandline("foo",cores=3), Commandline("foo") ]
    gen = CommandlineGenerator(list=clist)
    count = 0
    for g in gen:
        print(g,flush=True)
        if count==len(clist)+1:
            assert(False)
        count += 1
    print("seen %d commands" % count,flush=True)
    assert(count==len(clist))

class testGeneratorStuff():
    def testGeneratorListAdd(self):
        """testGeneratorListAdd: generate commands from a list that gets expanded, use nmax"""
        clist = [ Commandline("foo",cores=2), Commandline("foo",cores=3), Commandline("foo") ]
        gen = CommandlineGenerator(list=clist,nmax=len(clist)+1)
        count = 0
        for g in gen:
            count += 1; gen.list.append(5) # this should be in an inherited class
        print("seen %d commands" % count,flush=True)
        assert(count==len(clist)+1)

    def testGeneratorListFinish(self):
        gen = CommandlineGenerator(list=[ 
                Commandline("foo",cores=2), Commandline("foo",cores=3), Commandline("foo") ],
                                   nmax=0)
        count = 0; nstop = 6
        for g in gen:
            count += 1; gen.list.append(3*count)
            if count==nstop: gen.abort()
        print("seen %d commands" % count,flush=True)
        assert(count==nstop)

    def testGeneratorStalling(self):
        gen = CommandlineGenerator(list=[],nmax=0)
        rc = gen.next(); print(rc,flush=True)
        assert(rc["command"]=="stall")

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
        print(r,flush=True); assert(r=="a" and str(c)=="1")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print(r,flush=True); assert(r=="b" and str(c)=="1")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print(r,flush=True); assert(r=="c" and str(c)=="1")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print(r,flush=True); assert(r=="d" and str(c)=="1")
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
        print("<<r=%s>>,<<c=%s>>" % (r,str(c)),flush=True)
        assert(r=="a" and str(c)=="1")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print("<<r=%s>>,<<c=%s>>" % (r,str(c)),flush=True)
        assert(r=="b" and str(c)=="3")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print("<<r=%s>>,<<c=%s>>" % (r,str(c)),flush=True)
        assert(r=="c" and str(c)=="2")
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print("<<r=%s>>,<<c=%s>>" % (r,str(c)),flush=True)
        assert(r=="d" and str(c)=="5")
        try:
            rc = generator.next()
            assert(False)
        except:
            os.system("/bin/rm -f %s" % fn)
            assert(True)

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
        print("len:",len(generator),flush=True)
        assert(len(generator)==0)
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print(r,c,flush=True)
        assert(r=="stall")
        #
        generator.append( Commandline("foo") )
        # generator has one item
        print("len:",len(generator),flush=True)
        assert(len(generator)==1)
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print(r,c,flush=True)
        assert(r=="foo")
        # generator is empty again
        print("len:",len(generator),flush=True)
        assert(len(generator)==0)
        rc = generator.next(); r = rc["command"]; c = rc["cores"]
        print(r,c,flush=True)
        assert(r=="stall")
        generator.finish()
        # generator is empty and finished so it raises StopIteration
        try: 
            rc = generator.next()
            assert(False)
        except:
            assert(True)

class testDirectoryCommandlineGenerators():
    def setup(self):
        self.dirname = MakeRandomDir()
        print("running Directory Generator in <<%s>>" % self.dirname,flush=True)
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
            hostpool=HostPool( hostlist=HostListByName(debug=debug),
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
        print("files:",self.files,flush=True)
        assert(len(self.files)==len(self.nums)+1)
        # now process the files
        gen = DirectoryCommandlineGenerator(self.dirname,self.fileroot)
        for ig,g in enumerate( gen ):
            print(ig,g,flush=True)
        assert(ig==len(self.nums)-1)
    def testDirectoryCommandlineGeneratorJob(self):
        """testDirectoryCommandlineGeneratorJob: test finding commands in directory"""
        self.makefiles()
        print("files:",self.files,flush=True)
        assert(len(self.files)==len(self.nums)+1)
        # now process the files
        gen = DirectoryCommandlineGenerator(self.dirname,self.fileroot)
        j = self.makejob(gen)
        starttime = time.time()
        while True:
            r = j.tick(); print(r,flush=True)
            if r=="finished": break
            if time.time()-starttime>self.nsleep+len(self.nums)*j.delay+1:
                print("This is taking too long",flush=True); assert(False)
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
            print(ig,g,flush=True)
        assert(ig==len(self.nums)-1)
    def testDirectoryCommandlineGeneratorJobFromZero(self):
        """testDirectoryCommandlineGeneratorJob: test finding commands in directory"""
        # first we create the generator on an empty directory
        gen = DirectoryCommandlineGenerator(self.dirname,self.fileroot)
        j = self.makejob(gen)
        r = j.tick(); print(r,flush=True)
        assert(r=="stalling")
        # now actually make the files
        self.makefiles()
        print("files:",self.files,flush=True)
        assert(len(self.files)==len(self.nums)+1)
        # now process the files
        starttime = time.time()
        while True:
            r = j.tick(); print(r,flush=True)
            if r=="finished": break
            if time.time()-starttime>self.nsleep+len(self.nums)*j.delay+1:
                print("This is taking too long",flush=True)
                assert(False)
        assert(True)

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
            print(lc,flush=True)
            l = lc["command"]
            count += 1
        print("counted: %d, should be %d" % (count,self.ncommand),flush=True)
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
            print(count,flush=True)
            generator.append( Commandline(more_commands.next()) ) 
            if count==nmax:
                generator.abort()
                #generator.finish()
        assert(count==nmax)

class testCompletions():
    def setup(self):
        # get rid of old workdirs
        tmpdir = os.getcwd()+"/"+Executor.default_workdir()
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
        print("expected stamp:",task.completion.stampname(),flush=True)
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

class testTasksOnSingleNode():
    stampname = "pylauncher_tmp_singlenode_tasktest"
    def setup(self):
        os.system( "rm -f %s*" % RandomSleepTask.stamproot )
        tmpdir = os.getcwd()+"/"+Executor.default_workdir()
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir)
        self.pool = LocalHostPool(nhosts=1)
    def testLeaveStampOnOneNode(self):
        """testLeaveStampOnOneNode: leave a stamp on a one-node pool"""
        nsleep = 5
        start = time.time()
        t = RandomSleepTask(taskid=1,t=nsleep,
                            completion=FileCompletion(taskid=1,
                                                      stamproot=self.stampname),
                            debug="exec+task+ssh")
        print("starting task:",t,flush=True)
        t.start_on_nodes(pool=self.pool.request_nodes(1))
        assert(time.time()-start<1)
        time.sleep(nsleep+1)
        dircontent = os.listdir(t.completion.stampdir)
        print("looking for stamp <<%s>> in <<%s>>" % \
              (self.stampname,t.completion.stampdir),flush=True)
        print(sorted(dircontent),flush=True)
        stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
        print("stamps:",stamps,flush=True)
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
        print("stamps:",stamps,flush=True)
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
            if functools.reduce( lambda x,y: x and y,
                       [ t.hasCompleted() for t in tasks ] ): break
            if time.time()-start>nsleep+2:
                print("this is taking too long",flush=True)
                assert(False)
        dircontent = os.listdir(".")
        print("dir content:",sorted(dircontent),flush=True)
        stamps = [ f for f in dircontent if re.search(stamproot,f) ]
        print("stamps:",stamps,flush=True)
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
        print("stamps based on:",stamproot,flush=True)
        finished = [ False for i in range(self.ntasks) ]
        while True:
            print("tick",flush=True)
            if functools.reduce( lambda x,y: x and y,
                       [ t.hasCompleted() for t in tasks ] ): break
            if time.time()-start>nsleep+3:
                print("this is taking too long",flush=True)
                assert(False)
            time.sleep(1)
        dircontent = os.listdir(self.stampdir)
        stamps = [ f for f in dircontent if re.match("%s" % stamproot,f) ]
        print("stamps:",sorted(stamps),flush=True)
        assert(len(stamps)==self.ntasks)

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

def testHostPoolN():
    # get rid of old workdirs
    tmpdir = os.getcwd()+"/"+Executor.default_workdir()
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
    tmpdir = os.getcwd()+"/"+Executor.default_workdir()
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
            l = l.strip(); print(l,flush=True)
            assert(l==word)
    os.system("/bin/rm -f %s" % fn)
    assert(True)
    # cleanup
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)

def testTACChostlist():
    for h in HostListByName(debug="host"):
        print("hostfile line:",h,flush=True)
        assert( 'core' in h and 'host' in h )
        host = h["host"].split(".")
        #assert( len(host)>1 and host[1]==HostName() )

def testPEhostpools():
    """testPEhostpools: Test that we get the right number of cores on the TACC hosts"""
    # get rid of old workdirs
    tmpdir = os.getcwd()+"/"+Executor.default_workdir()
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
    elif cluster in ["stampede2","stampede2-knl","stampede2-skx"]:
        assert(len(pool)>0)
    elif cluster=="longhorn":
        assert(len(pool)%40==0)
    else:
        print("Detecting host",cluster,flush=True)
        assert(True)
    # cleanup
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)

def testHostPoolWorkdirforcing():
    os.system("/bin/rm -rf "+Executor.default_workdir())
    os.mkdir(Executor.default_workdir())
    try:
        exc = Executor()
        assert(False)
    except:
        assert(True)
    exc = Executor(force_workdir=True)
    assert(True)

def testTaskQueue():
    """testTaskQueue: queue and detect a task in a queue
    using the default task prefixer and completion tester"""
    # get rid of old workdirs
    tmpdir = os.getcwd()+"/"+Executor.default_workdir()
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
    print("found completed:",complete_id,flush=True)
    assert(complete_id==t_id)
    task.completion.cleanup()
    assert(True)
    # cleanup
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)

def testTaskQueueWithLauncherdir():
    """testTaskQueueWithLauncherdir: same, but test correct use of launcherdir"""
    # get rid of old workdirs
    tmpdir = os.getcwd()+"/"+Executor.default_workdir()
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
    print("completed:",complete_id,flush=True)
    assert(complete_id==t_id)
    files = os.listdir(dirname)#queue.launcherdir)
    print(files,flush=True)
    assert(len(files)==1)
    os.system("/bin/rm -rf %s" % dirname)
    assert(True)
    # cleanup
    if os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)

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
        print("%d s/b %d" % (count,self.ncommand),flush=True)
        assert(count==self.ncommand)
    def testFileTaskGeneratorIteratable(self):
        """testFileTaskGeneratorIteratable: test that the taskgenerator can deal with a file"""
        count = 0
        for t in TaskGeneratorIterate( TaskGenerator( 
                FileCommandlineGenerator(self.fn,cores=1,debug="command"),
                debug="task") ):
            count += 1
        print("%d s/b %d" % (count,self.ncommand),flush=True)
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
                print("this is taking too long",flush=True)
                assert(False)
        print("%d s/b %d" % (count,self.ncommand),flush=True)
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
        print("count %d s/b %d" % (count,nmax),flush=True)
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
        print("count %d s/b %d" % (count,nmax),flush=True)
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
        files = os.listdir(self.dir); print(files,flush=True)
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
        print("executed %d plus skipped %d s/b %d" % (count,len(skip),self.ncommand),flush=True)
        assert(count+len(skip)==self.ncommand)

def testModuleCommandline():
    ntasks = 40; fn = "modtest"
    MakeRandomSleepFile(fn,ntasks)
    os.system("/bin/rm -f %s" % fn)
    assert(True)

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
    wd = "a%d" % RandomID(); print("testing with executor tmpdir",wd,flush=True)
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

def testLocalExecutor():
    """testLocalExecutor: check that local execution works"""
    wd = NoRandomDir()
    x = LocalExecutor(debug="exec",workdir=wd)
    touched = RandomFile()
    # test the basic mechanisms
    x.execute("touch %s" % touched)
    print(os.listdir(x.workdir),flush=True)
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
            print("available hosts:",hosts,flush=True)
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
                            line = line.strip(); print("<<%s>> <<%s>>" % (line,hosts[1]),flush=True)
                            assert(line==hosts[1])
                            break
                except: 
                    assert(False)
            else:
                command = "cat %s/%s" % (pwd,fn)
                p = subprocess.Popen(command,shell=True,stdout=subprocess.PIPE)
                hostread = p.communicate()[0].strip(); print(hostread,flush=True)
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
        print("elapsed time for an ssh",elapsed,flush=True)
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
        print("ps lines:",flush=True)
        for p in psread:
            print(p,flush=True)
        print(len(psread),flush=True)
        assert(len(psread)==2*n) # once wrapped with chmod 777, once by itself.
    def testSSHLeaveStamp(self):
        """testSSHLeaveStamp: leave a single stampfile"""
        nsleep = 4; taskid = RandomID()
        taccpool = DefaultHostPool(commandexecutor=SSHExecutor())
        start = time.time()
        t = RandomSleepTask(taskid=taskid,t=nsleep,stamproot=self.stampname,debug="task")
        nodepool = taccpool.request_nodes(1)
        assert(nodepool is not None)
        print("available pool:",str(nodepool),flush=True)
        assert(nodepool.offset==0)
        t.start_on_nodes(pool=nodepool)
        taccpool.occupyNodes(nodepool,t.taskid)
        time.sleep(nsleep+1)
        curdir = t.completion.stampdir; dircontent = os.listdir(curdir)
        print("looking for stamps in <<%s>> and found <<%s>>" % \
              (curdir,sorted(dircontent)),flush=True)
        stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
        print("stamps:",sorted(stamps),flush=True)
        wanted = self.stampname+str(taskid); print("wanted:",wanted,flush=True)
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
                print("available pool:",str(nodepool),flush=True)
                assert(nodepool.offset==itask)
                t.start_on_nodes(pool=nodepool)
                taccpool.occupyNodes(nodepool,t.taskid)
            interval = time.time()-start; print("this took %e seconds" % interval,flush=True)
            assert(interval<ntasks*.5)
            time.sleep(nsleep+1)
            dir = t.completion.stampdir; dircontent = os.listdir(dir)
            print("looking for stamps and found:",sorted(dircontent),flush=True)
            stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
            print("stamps:",sorted(stamps),flush=True)
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
        print("stampdir:",sorted(os.listdir(t.completion.stampdir)),flush=True)
        dircontent = os.listdir(os.getcwd())
        print("looking for result locally and found <<%s>>" % sorted(dircontent),flush=True)
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
                print("available pool:",str(nodepool),flush=True)
                assert(nodepool.offset==itask)
                t.start_on_nodes(pool=nodepool)
                taccpool.occupyNodes(nodepool,t.taskid)
            interval = time.time()-start; print("this took %e seconds" % interval,flush=True)
            assert(interval<ntasks*.5)
            time.sleep(nsleep+1)
            dir = t.completion.stampdir; dircontent = os.listdir(dir)
            print("looking for stamps and found:",sorted(dircontent),flush=True)
            stamps = [ f for f in dircontent if re.match("%s" % self.stampname,f) ]
            print("stamps:",sorted(stamps),flush=True)
            assert(len(stamps)==ntasks)
        else: assert(True)
    def testRemoteSSHEnv(self):
        """testRemoteSSHEnv: This tests whether the environment is propagated.
        We set an environment variable, and start a process that prints it.
        """
        hosts = DefaultHostPool().unique_hostnames()
        if len(hosts)>1:
            print("available hosts:",hosts,flush=True)
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
                            line = line.strip(); print("<<%s>>" % line,flush=True)
                            assert(line==val)
                            break
                except: 
                    assert(False)
            else:
                command = "cat %s/%s" % (pwd,fn)
                p = subprocess.Popen(command,shell=True,stdout=subprocess.PIPE)
                hostread = p.communicate()[0].strip(); print(hostread,flush=True)
                assert(hostread==val)
            os.system("/bin/rm -f %s" % fn)
        else: assert(True)

class testLeaveSSHOutput():
    def setup(self):
        ndirs = 3
        self.dirs = [ RandomDir() for d in range(ndirs) ]
        print("creating directories:",self.dirs,"in",os.getcwd(),flush=True)
        for d in self.dirs:
            absdir = os.getcwd()+"/"+d
            if os.path.isfile(absdir):
                raise LauncherException("Problem running this test")
            if os.path.isdir(absdir):
                shutil.rmtree(absdir)
            print("creating",absdir,flush=True)
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
        print("curdir  :",sorted(os.listdir(os.getcwd())),flush=True)
        print("available",self.dirs,flush=True)
        taskid = RandomID()
        start = time.time()
        tmpdir = self.dirs[0]; tmpfile = RandomFile(); absdir = os.getcwd()+"/"+tmpdir
        print("going to create %s in %s" % (tmpfile,tmpdir),flush=True)
        t = Task( Commandline("cd %s; touch %s" % (absdir,tmpfile)),
                  taskid=taskid,
                  completion=FileCompletion(taskid=taskid),debug="task+exec+ssh")
        nodepool = self.taccpool.request_nodes(1)
        assert(nodepool is not None)
        t.start_on_nodes(pool=nodepool)
        self.taccpool.occupyNodes(nodepool,t.taskid)
        time.sleep(1)
        assert(t.completion.test())
        print("stampdir:",sorted(os.listdir(t.completion.stampdir)),flush=True)
        dircontent = os.listdir(absdir)
        print("looking for result in <<%s>> and found <<%s>>" % \
              (absdir,sorted(dircontent)),flush=True)
        assert(tmpfile in dircontent)
    def testSSHLeaveResultRelative(self):
        """testSSHLeaveResultRelative: create a file in a directory and detect that it's there"""
        print("curdir  :",sorted(os.listdir(os.getcwd())),flush=True)
        print("available",self.dirs,flush=True)
        taskid = RandomID()
        start = time.time()
        tmpdir = self.dirs[0]; tmpfile = RandomFile(); absdir = os.getcwd()+"/"+tmpdir
        print("going to create %s in %s" % (tmpfile,tmpdir),flush=True)
        t = Task( Commandline("cd %s; touch %s" % (tmpdir,tmpfile)),
                  taskid=taskid,
                  completion=FileCompletion(taskid=taskid),debug="task+exec+ssh")
        nodepool = self.taccpool.request_nodes(1)
        assert(nodepool is not None)
        t.start_on_nodes(pool=nodepool)
        self.taccpool.occupyNodes(nodepool,t.taskid)
        time.sleep(1)
        assert(t.completion.test())
        print("stampdir:",sorted(os.listdir(t.completion.stampdir)),flush=True)
        dircontent = os.listdir(absdir)
        print("looking for result in <<%s>> and found <<%s>>" % \
              (absdir,sorted(dircontent)),flush=True)
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
        content0 = os.listdir(self.dirs[0]); print(sorted(content0),flush=True)
        stamps = [ f for f in content0 if re.search("expire",f) ]
        assert(len(stamps)==ntasks)

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
        print("line1:", line1,flush=True)
        out1 = RandomFile(); out_handle1 = open(out1,"w")
        ibrun_executor.execute(line1,pool=nodes1,stdout=out_handle1)
        pool.occupyNodes(nodes1,1)
        # put a task on the other half of the nodes
        line2 = os.getcwd()+"/"+self.testprog_name
        nodes2 = pool.request_nodes(nnodes)
        print("line2:", line2,flush=True)
        out2 = RandomFile(); out_handle2 = open(out2,"w")
        ibrun_executor.execute(line2,pool=nodes2,stdout=out_handle2)
        pool.occupyNodes(nodes2,2)
        # there should be no nodes left
        no_nodes = pool.request_nodes(1); print(no_nodes,flush=True)
        assert(no_nodes is None)
        # see if the result was left
        time.sleep(nslp)
        assert( os.path.isfile(out1) )
        with open(out1,"r") as output1:
            t = 0
            for line in output1:
                line = line.strip()
                print("output1:",line,flush=True)
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
                print("output2:",line,flush=True)
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
            print("tick:",job.tock,"elapsed: %5.3e" % elapsed,"result:",res,flush=True)
            if res=="finished": break
            elif re.match("^expire",res):
                print(res,flush=True)
            if elapsed>2+ntasks*job.delay+self.maxsleep:
                estr = "This is taking too long: %d sec for %d tasks" % (int(elapsed),ntasks)
                print(estr,flush=True)
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
            print("tick:",job.tock,"elapsed: %5.3e" % elapsed,"result:",res,flush=True)
            if res=="finished": break
            elif re.match("^expire",res):
                print(res,flush=True)
            if elapsed>2+ntasks*job.delay+self.maxsleep:
                estr = "This is taking too long: %d sec for %d tasks" % (int(elapsed),ntasks)
                print(estr,flush=True)
                raise LauncherException(estr)
        if elapsed<self.maxsleep:
            print("This finished too quickly: %d s/b %d" % (elapsed,self.maxsleep),flush=True)
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
        print("Making %d commands" % ncommand,flush=True)
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
            print("Hm. We managed to reuse a workdir",flush=True)
            result = False # this should except out becuase of the workdir
        except: 
            print("Exception: attempting to reuse workdir",flush=True)
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
        print("Making %d commands" % ncommand,flush=True)
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
        print(job.final_report(),flush=True)
        completed = job.queue.completed
        noncomp = job.queue.running+job.queue.queue
        print("lengths of completed / noncomp",len(completed),len(noncomp),flush=True)
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
            print("tick:",job.tock,"elapsed: %5.3e" % elapsed,"result:",res,flush=True)
            if res=="finished": break
            elif re.match("^expire",res):
                print(res,flush=True)
            if elapsed>2+ntasks*job.delay+self.maxsleep:
                estr = "This is taking too long: %d sec for %d tasks" % (int(elapsed),ntasks)
                print(estr,flush=True)
                assert(False)
        duration = time.time()-starttime; print(duration,flush=True)
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
        duration = time.time()-starttime; print(duration,flush=True)
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
        duration = time.time()-starttime; print(duration,flush=True)
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
        print("tasks completed %d s/b %d" % (job.completed,self.ncommand),flush=True)
        assert(job.completed==self.ncommand)

class testIBRUNLauncherJobs():
    def setup(self):
        self.launcherdir = NoRandomDir()
        self.hostpool = HostPool( hostlist=HostListByName(debug="host"),
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
            print("tick:",job.tock,"elapsed: %5.3e" % elapsed,"result:",res,flush=True)
            if res=="finished": break
            elif re.match("^expire",res):
                print(res,flush=True)
            if elapsed>2+ntasks*job.delay+self.maxsleep:
                estr = "This is taking too long: %d sec for %d tasks" % (int(elapsed),ntasks)
                print(estr,flush=True)
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
            print("tick:",job.tock,"elapsed: %5.3e" % elapsed,"result:",res,flush=True)
            if res=="finished": break
            elif re.match("^expire",res):
                print(res,flush=True)
            if elapsed>2+ntasks*job.delay+self.maxsleep:
                estr = "This is taking too long: %d sec for %d tasks" % (int(elapsed),ntasks)
                print(estr,flush=True)
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
    abs_tmpdir = os.getcwd()+"/"+tmpdir; print("working dir:",abs_tmpdir,flush=True)
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
    dircontent = os.listdir("."); print(". :",sorted(dircontent),flush=True)
    dircontent = os.listdir(".."); print(".. :",sorted(dircontent),flush=True)
    dircontent = os.listdir(abs_tmpdir); print(abs_tmpdir,":",sorted(dircontent),flush=True)
    assert(tmpfile in dircontent)
    os.system("rm -rf %s" % abs_tmpdir)

def testParamJob():
    # first make a C program that parses its argument
    testdir = MakeRandomDir()
    testprog_name = "print_program"
    print("Making c program <<%s>> in <<%s>>" % (testprog_name,testdir),flush=True)
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
#     runtime = time.time()-tstart; print(nsleep,runtime,flush=True)
#     assert(runtime>2*nsleep)

