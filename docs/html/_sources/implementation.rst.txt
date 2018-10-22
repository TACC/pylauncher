Implementation
--------------

.. automodule:: pylauncher
   :undoc-members:
   :show-inheritance:

======================
Commandline generation
======================

The term 'commandline' has a technical meaning:
a commandline is a two-element list or a tuple where the first member is the
Unix command and the second is a core count. These commandline tuples are generated
by a couple of types of generators.

The ``CommandlineGenerator`` base class handles the 
basics of generating commandlines.
Most of the time you will use the derived class ``FileCommandlineGenerator`` which
turns a file of Unix commands into commandlines.

Most of the time a commandline generator will run until some supply of 
commands run out. However, 
the ``DynamicCommandlineGenerator`` class runs forever, 
or at least until you tell it to stop, so it is good for
lists that are dynamically replenished.

.. autoclass:: CommandlineGenerator
   :members: finish, next
.. autoclass:: CommandlineGenerator
   :members:
.. autoclass:: FileCommandlineGenerator
   :show-inheritance:
.. autoclass:: DynamicCommandlineGenerator
   :show-inheritance:
   :members:
.. autoclass:: DirectoryCommandlineGenerator
   :show-inheritance:
   :members:

===============
Host management
===============

We have an abstract concept of a node, which is a slot for a job. 
Host pools are the management structure for these nodes:
you can query a host pool for sufficient nodes to run a multiprocess job.

A host pool has associated with it an executor object, which represents
the way tasks (see below) are started on nodes in that pool. Executors are also
discussed below.

.. autoclass:: Node
   :members:
.. autoclass:: HostList
   :members:
.. autoclass:: HostPoolBase
   :members:
.. autoclass:: HostPool
   :show-inheritance:
   :members:
.. autoclass:: HostLocator
   :show-inheritance:
   :members:
.. autoclass:: DefaultHostPool
   :show-inheritance:

===============
Task management
===============

Tasks are generated internally from a ``TaskGenerator`` object that
the user can specify. The ``TaskQueue`` object is created internally
in a ``LauncherJob``.  For the ``completion`` argument of the ``TaskGenerator``,
see below.

.. autoclass:: Task
   :members:
.. autoclass:: TaskQueue
   :members:
.. autoclass:: TaskGenerator
   :members:
.. autofunction:: TaskGeneratorIterate

"""""""""
Executors
"""""""""

At some point a task needs to be executed. It does that by applying the ``execute``
method of the ``Executor`` object of the ``HostPool``. (The thinking
behind attaching the execution to a host pool is that
different hostpools have different execution mechanisms.)
Executing a task takes a commandline and a host locator on which to execute it;
different classes derived from ``Executor`` correspond to different spawning 
mechanisms.

.. autoclass:: Executor
   :members:
.. autoclass:: LocalExecutor
   :show-inheritance:
.. autoclass:: SSHExecutor
   :show-inheritance:
   :members:
.. autoclass:: IbrunExecutor
   :show-inheritance:
   :members:


"""""""""""""""
Task Completion
"""""""""""""""

Task management is largely done internally. The one aspect that a user
could customize is that of the completion mechanism: by default each
commandline that gets executed leaves a zero size file behind that is
branded with the task number. The TaskQueue object uses that to detect
that a task is finished, and therefore that its Node objects can be
released. 

.. autoclass:: Completion
   :members:
.. autoclass:: FileCompletion
   :show-inheritance:
   :members:

Task generators need completions dynamically generated since they need
to receive a job id. You could for instance specify code such as the 
following; see the example launchers.

::

  completion=lambda x:FileCompletion( taskid=x,
               stamproot="expire",stampdir="workdir")


====
Jobs
====

All of the above components are pulled together in the LauncherJob class.
Writing your own launcher this way is fairly easy;
see the TACC section for some examples of launchers.

.. autoclass:: LauncherJob
   :members: tick, run

