# Customization for PBS and Non-TACC integration of pylauncher. 
Christopher Blanton, Ph.D.
chris.blanton@gatech.edu


The expansion of pylauncher to the PBS systems and non-TACC systems has 
requested some several alterations, which are detailed below:


# PBSHostList

A class `PBSHostList(HostList)` was created. This class uses the `PBS_NODEFILE` to generate the HostList.

# ClusterName

The `ClusterName` function was modified to detect Georgia Institute of Technology's PACE system. 

# HostListByName

The `HostListByName` function was modiifed to use the `PBSHostList` in the case that the system was `pace`

# Generic MPIExecutor and MPILauncher

Since TACC has the Ibrun command for MPI jobs, the Ibrun command is not useful for sites which do not use it. 
For sites such as Georgia Tech, a generic version was created to directly use `mpirun` in these cases.
The `MPILauncher` has the additional keywork `hfswitch` to be used for selecting the `mpirun` option that specifies the hostname 
since hostfiles (machinefiles) need to be used so as the job does not use the scheduler integration and oversubscribe the system
during multiple simultaneous runs.





