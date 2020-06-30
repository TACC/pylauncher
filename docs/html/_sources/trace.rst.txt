Tracing and profiling
---------------------

It is possible to generate trace output during a run and profiling
(or summary) information at the end.

============
Trace output
============

.. automodule:: pylauncher3

You can get various kinds of trace output on your job. This is done by
specifying a ``debug=....`` parameter to the creation of the various classes.
For the easy case, pass ``debug="job+host+task"`` to a launcher object.

Here is a list of the keywords and what they report on:

* host: for ``HostPool`` objects.
* command: for ``CommandlineGenerator`` objects.
* task: for ``Task`` and ``TaskGenerator`` objects.
* exec: for ``Executor`` objects. For the SSHExecutor this prints out the contents of the temporary file containing the whole environment definition.
* ssh: for ``SSHExecutor`` objects.
* job: for ``LauncherJob`` objects.

===============
Final reporting
===============

Various classes can produce a report. This is intended to be used at the
end of a job, but you can do it really at any time. The predefined launchers
such as ``ClassicLauncher``
print out this stuff by default.

.. autoclass:: HostPoolBase
   :members: final_report
.. autoclass:: TaskQueue
   :members: final_report
.. autoclass:: LauncherJob
   :members: final_report

