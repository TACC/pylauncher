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

