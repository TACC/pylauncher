##
## Computational server: pylauncher job
## accepting commands from a socket
##
import socket
from pylauncher import *

class SocketCommandlineGenerator(CommandlineGenerator):
    def __init__(self,**kwargs):
        nmax = kwargs.pop("nmax",-2)
        if nmax!=-2:
            raise LauncherException("Can not specify nmax for SocketCommandlineGenerator")
        CommandlineGenerator.__init__(self,nmax=0,**kwargs)
        HOST = 'localhost'
        PORT = 5007
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((HOST, PORT))
        self.socket.listen(1)
        self.conn, addr = self.socket.accept()
    def next(self):
        data = self.conn.recv(1024)
        if not data:
            self.conn.close()
            raise StopIteration
        else:
            print "received command <<%s>>" % data
            self.conn.send("ACK")
            return Commandline(data)

def SocketLauncher(**kwargs):
    """A LauncherJob that accepts its commands over a socket.
    This is largely identical to the ClassicLauncher function,
    except for the "taskgenerator" argument, which uses the
    SocketCommandLineGenerator class.

    :param cores: number of cores per commandline (keyword, optional, default=1)
    :param workdir: (keyword, optional, default=pylauncher_tmp_jobid) directory for output and temporary files
    :param debug: debug types string (optional, keyword)
    """
    jobid = JobId()
    debug = kwargs.pop("debug","")
    workdir = kwargs.pop("workdir","pylauncher_tmp"+str(jobid) )
    cores = kwargs.pop("cores",1)
    job = LauncherJob(
        hostpool=HostPool( hostlist=HostListByName(),
            commandexecutor=SSHExecutor(workdir=workdir,debug=debug), debug=debug ),
        taskgenerator=TaskGenerator( 
            SocketCommandlineGenerator(debug=debug),
            completion=lambda x:FileCompletion( taskid=x,
                                    stamproot="expire",stampdir=workdir),
            debug=debug ),
        debug=debug,**kwargs)
    job.run()
    print job.final_report()

SocketLauncher()
