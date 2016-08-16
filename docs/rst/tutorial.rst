A quick tutorial
================

=====
Setup
=====

You need to have the files ``pylauncher.py`` and ``hostlist.py`` in your ``PYTHONPATH``.
If you are at TACC, do ``module load pylauncher`` and all is good.

===============
Batch operation
===============

The most common usage scenario is to use the launcher to bundle many small jobs
into a single batch submission on a cluster. In that case, just put

  ::

  module load python

  ::

  python your_launcher_file.py

in the jobscript. 

If you are using TACC's stampede cluster, and you want to run the launcher script
on the Intel Xeon PHI co-processor, do

  ::

  micrun /mic/python your_launcher_file.py

where '/mic/python' is the path to a python that is compiled for MIC.
Currently no such python is officially available on Stampede.


========
Examples
========

There is an ``examples`` subdirectory with some simple scenarios
of how to invoke the pylauncher.

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

.. literalinclude:: ../../examples/parallellines
   :lines: 1-10

This example uses a provided program, ``parallel.c`` of two parameters:

* the job number
* the number of seconds running time

The program will report the size of its communicator, that is,
on how many cores it is running.
