Introduction and general usage
------------------------------

.. automodule:: pylauncher3

This is the documentation of the pylauncher utility by Victor Eijkhout.

==========
Motivation
==========

There are various scenarios where you want to run
a large number of serial or low-corecount parallel jobs.
Many cluster scheduling systems do not allow you to 
submit a large number of small jobs (and it would probably
lower your priority!) so it would be a good idea
to package them into one large parallel job. 

Let's say that you have 4000 serial jobs, and your cluster allows
you to allocate 400 cores, then packing up the serial jobs could
be executed on those 400 cores, in approximately the time of 10 serial jobs.

The tool to do this packing is called a *parametric job launcher*.
The 'parametric' part refers to the fact that most of the time your 
serial jobs will be the same program, just invoked with a different input parameter.
One also talks of a 'parameter sweep' for the whole process.

A simple launcher scenario would take a file with command lines,
and give them out cyclicly to the available cores. This mode
is not optimal, since one core could wind up with a few processes
that take much longer than the others. Therefore we want a dynamic launcher
that keeps track of which cores are free, and schedules jobs there.

In a very ambitious scenario, you would not have a static list of 
commands to execute, but new commandlines would be generated 
depending on the ones that are finished. For instance, you could have
a very large parameter space, and the results of finished jobs
would tell you what part of space to explore next, and what part
to ignore.

The pylauncher module supports such scenarios.

======================================================
Here's what I want to know: do I have to learn python?
======================================================

Short answer: probably not. The pylauncher utility is
written in python, and to use it you have to write a few lines of python.
However, for most common scenarios there are example scripts that you
can just copy.

Longer answer: only if you want to get ambitious. 
For common scenarios there are single function calls which you
can copy from example scripts. However, the launcher is highly customizable,
and to use that functionality you need to understand something about python's
classes and you may even have to code your own event loop. That's the price you
pay for a very powerful tool.

===========
Realization
===========

The pylauncher is a very customizable launcher utility. 
It provides base classes and routines that take care of 
most common tasks; by building on them you can tailor
the launcher to your specific scenario.

Since this launcher was developed for use at the Texas Advanced Computing Center,
certain routines are designed for the specific systems in use there.
In particular, processor management is based on the 
SGE and SLURM job schedulers and the environment variables they define.
By inspecting the source it should be clear how to customize 
the launcher for other schedulers and other environments.

If you write such customizations, please contact the author.
Ideally, you would fork the repository
https://github.com/TACC/pylauncher
and generate a pull request.

