A quick tutorial
================

=====
Setup
=====

You need to have the files ``pylauncher3.py`` and ``hostlist.py`` in your ``PYTHONPATH``.
If you are at TACC, do ``module load pylauncher`` and all is good.

===============
Batch operation
===============

The most common usage scenario is to use the launcher to bundle many small jobs
into a single batch submission on a cluster. In that case, put::

  module load python3
  python3 your_launcher_file.py

in the jobscript.
Note that python is started sequentially here;
all parallelism is handled inside the pylauncher code.

====================
Parallelism handling
====================

Parallelism with the pylauncher is influenced by the following:

* The SLURM/PBS node and core count
* The OMP_NUM_PROCS environment variable
* Core count specifications in the pylauncher python script
* Core count specifications in the commandlines file.

The most important thing to know is that the pylauncher uses the SLURM/PBS parameters
to discover how many cores there are available.
It is most convenient to set these parameters to the number of actual cores present.
So if you have a 40-core node, set ``tasks-per-node=40``. This tells the pylauncher
that there are 40 cores; it does not imply that there will be 40 tasks.

If each of your commandlines needs to run on a single core, this is all you need to
know about parallelism.

----------------
Affinity
----------------

There is an experimental option ``numactl="core"``.

========
Examples
========

There is an ``examples`` subdirectory with some simple scenarios
of how to invoke the pylauncher. We start with a number of launchers
that run inside a parallel (SLURM/SGE/PBS) job.

----------------
Single-core jobs
----------------

In the simplest scenario, we have a file of commandlines, 
each to be executed on a single core.

.. literalinclude:: ../../examples/example_classic_launcher.py

where the commandlines file is:

.. literalinclude:: ../../examples/commandlines
   :lines: 1-10

--------------------------------
Constant count multi-core jobs
--------------------------------

The next example uses again a file of commandlines, but now the
launcher invocation specifies a core count that is to be used for
each job.

.. literalinclude:: ../../examples/example_core_launcher.py

You still need to set ``OMP_NUM_PROCS`` to tell your code how many cores it can take.

Also note that this core count is not reflected in your SLURM setup:
as remarked above that only tells the pylauncher how many cores there are
on each node (``--tasks-per-node``) or in total for your whole job (``-n``).

------------------------------
Variable count multi-core jobs
------------------------------

If we have multithreaded jobs, but each has its own core count, 
we add the core count to the file of commandlines, and we tell
the launcher invocation that that is where the counts are found.

.. literalinclude:: ../../examples/example_variable_core_launcher.py

.. literalinclude:: ../../examples/corecommandlines
   :lines: 1-10

-----------------
MPI parallel jobs
-----------------

If your program uses the MPI library and you want to run multiple
instances simultaneously, use the ``IbrunLauncher``.

.. literalinclude:: ../../examples/example_shifted_ibrun.py

Each commandline needs to start with a number indicating
on how many cores the command is to run:

.. literalinclude:: ../../examples/parallellines
   :lines: 1-10

This example uses a provided program, ``parallel.c`` of two parameters:

* the job number
* the number of seconds running time

The program will report the size of its communicator, that is,
on how many cores it is running.

----------------
Local jobs
----------------

If you own your computer and you want to run the parallel
the parameter sweep locally, use the ``LocalLauncher``

.. literalinclude:: ../../examples/example_.py

Two parameters:

* name of a file of commandlines
* a count of how many jobs you want to run simultaneously, typically
  the number of cores of your machine.

----------------
Remote jobs
----------------

The launchers so far spawned all jobs on the machine where the launcher python script
is running. It is possible to run the python script in one location (say, a container)
while spawning jobs elsewhere. First, the ``RemoteLauncher`` takes a hostlist
and spawns jobs there through an ssh connection::

  def RemoteLauncher(commandfile,hostlist,**kwargs)

Optional arguments:

* ``workdir`` : location for the temporary files
* ``ppn`` : how many jobs can be fitted on any one of the hosts
* ``cores`` : number of cores allocated to each job

  ::

  def IbrunRemoteLauncher(commandfile,hostlist,**kwargs)

Same arguments as the ``RemoteLauncher``, now every job is start as an MPI execution.

----------------
Job timeout
----------------

If individual tasks can take a varying amount of time and you may want
to kill them when they overrun some limit, you can add the

  ::

  taskmaxruntime=30

option to the launcher command.

.. literalinclude:: ../../examples/example_truncate_launcher.py

----------------
Job ID
----------------

The macro

  ::

  PYL_ID

gets expanded to the task ID on the commandline.

----------------
Job restarting
----------------

If your job runs out of time, it will leave a file ``queuestate`` that
describes which tasks were completed, which ones were running, and
which ones were still scheduled to fun. You can submit a job using the
``ResumeClassicLauncher``:

.. literalinclude:: ../../examples/resume/example_resume_launcher.py
