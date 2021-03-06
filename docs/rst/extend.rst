=======================================================
TACC specifics and extendability to other installations
=======================================================

The pylauncher source has a number of classes and routines
that are tailored to the use at the Texas Advanced Computing Center.
For starters, there are two classes derived from ``HostList``,
that parse the hostlists for the SGE and SLURM scheduler.
If you use Load Leveler or PBS, you can write your own
using these as an example.

.. automodule:: pylauncher3

.. autoclass:: SGEHostList
   :show-inheritance:
.. autoclass:: SLURMHostList
   :show-inheritance:
.. autofunction:: HostListByName
.. autoclass:: DefaultHostPool
   :show-inheritance:

Two utility functions may help you in writing customizations.

.. autofunction:: HostName
.. autofunction:: ClusterName
.. autofunction:: JobId

==============
TACC launchers
==============

.. autofunction:: ClassicLauncher
.. autofunction:: IbrunLauncher
.. autofunction:: MICLauncher
