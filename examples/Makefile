################################################################
####
#### Makefile for the pylauncher examples
#### pylauncher is copyright Victor Eijkhout 2010-2021
####
################################################################

info ::
	@echo "================================================================"
	@echo " This makefile tries to make it easy to run and submit example programs"
	@echo " supported clusters: stampede2 ls5"
	@echo "================================================================"
	@echo 
	@echo "Available make rules:"

EXECUTABLE = example_classic_launcher
SSH =
RUN = python
NODES = 2
CORESPERNODE = 16
QUEUE = development
info ::
	@echo 
	@echo "make submit"
	@echo "    [EXECUTABLE=... (default: ${EXECUTABLE})]"
	@echo "    [NODES=... (default: ${NODES})] [CORESPERNODE=... (default: ${CORESPERNODE})]"
	@echo "    [QUEUE=... (default: ${QUEUE})]"
	@echo "  this submits a jobscript (see jobscr.hostname) to the queue"
	@echo "  available programs:"
	@echo "    example_classic_launcher : single core jobs, found in ""commandlines"""
	@echo "    example_core_launcher : mult core jobs (constant count), found in ""commandlines"""
	@echo "    example_variable_core_launcher : variable core jobs, found in ""corecommandlines"""
	@echo "(note: remove the project line or replace by your own!)"
#make ${${EXECUTABLE}_dependencies}
submit :
	@export HOSTNAME=`hostname -f | awk -F "." '{print $$2}'` ; \
	  export found="no" ; \
	  case $$HOSTNAME in \
	    ( stampede2 ) export found="yes" ;; \
	    ( ls5 ) export found="yes" ;; \
	    esac ; \
	  if [ "$$found" = "no" ] ; then echo "Unknown host `hostname -f`" ; exit 1 ; fi ; \
	  echo "submitting ${EXECUTABLE}  on  $$HOSTNAME" ; \
	  eval export CORES=$$[ ${CORESPERNODE}*${NODES} ] ; \
	  export QUEUE=`if [ $$CORES -le 256 ] ; then echo development ; else echo normal ; fi` ; \
	  cat jobscript_template.$$HOSTNAME | sed -e "s/SSH/${SSH}/" -e "s/RUN/${RUN}/" \
	        -e "s/EXECUTABLE/${EXECUTABLE}/" \
	        -e "s/NODES/${NODES}/" -e "s/CORES/$$CORES/" -e "s/QUEUE/$$QUEUE/" \
	        > jobscript_generated ; \
	  sbatch jobscript_generated
example_shifted_ibrun_dependencies = parallel

CPROGRAMS = parallel randomaction
info ::
	@echo 
	@echo "make PROGRAM"
	@echo "    with C programs: ${CPROGRAMS}"
	@echo "    compiled with WAIT=SLURM_NPROCS"
.SECONDEXPANSION:
.PHONY: randomaction
parallel randomaction :
	@slurm=${SLURM_NPROCS} && slurm=$${slurm:=40} \
	&& wait=${WAIT} && wait=$${wait:=$${slurm}} \
	&& echo "compile $@ with wait=$$wait" \
	&& mpicc -o $@ $@.c -DWAIT=$${wait:=20}
clean ::
	@rm -f ${CPROGRAMS}

info ::
	@echo 
	@echo "make unittests"
	@echo "  this submits a unittest run (nosetests pylauncher.py) to the queue"
unittests :
	@ln -s ../pylauncher.py pylauncher.py
	@make submit RUN=nosetests EXECUTABLE=pylauncher

info ::
	@echo
	@echo "make commandlines [COVERAGE=...] [ NCORES=...] [TIME=...] [COMMAND=...]"
	@echo "    number of jobs = COVERAGE * NCORES"
	@echo "    values: ${COVERAGE} ${NCORES}"
	@echo "make randomcommandlines : use"
	@echo "    COMMAND=\"mkdir -p random/PYL_ID && cd random/PYL_ID && ../../randomaction PYL_ID > random.out\""
NCORES = ${SLURM_NPROCS}
TIME = 20
COVERAGE = 4
COMMAND = sleep
.PHONY : commandlines
commandlines :
	@export number_of_jobs=$$[ ${COVERAGE} * ${NCORES} ] \
	&& echo "make $$number_of_jobs commandlines" \
	&& PYTHONPATH=..:${PYTHONPATH} python3 make_commandlines.py "${COMMAND}" $$number_of_jobs 1 $$[ 2*${TIME} ]
.PHONY: randomcommandlines
randomcommandlines :
	@make --no-print-directory commandlines \
	    COVERAGE=${COVERAGE} NCORES=${NCORES} \
	    COMMAND="mkdir -p random/PYL_ID && cd random/PYL_ID && ../../randomaction PYL_ID > random.out"
clean ::
	@rm -rf random

info ::
	@echo 
	@echo "make clean"

clean ::
	@for d in "./" "./resume" "./sockets" ; do \
	  ( cd $$d ; \
	    /bin/rm -rf *.pyc *~ *.o *.log \
	      pylauncher_tmp* pylaunchertest* pylauncher*.{e,o}[0-9]* ${HOME}/pylauncher_tmp* \
	      expire* sleepexpire* tmpdir* tasktest* dirtest queuestate* pytmp* \
	      jobscript_generated ; ) ; done
#	@cd sockets ; make clean
