################################################################
####
#### Makefile for the pylauncher examples
#### pylauncher is copyright Victor Eijkhout 2010-2023
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
RUN = python3
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
NAME = 
script :
	@export HOSTNAME=`hostname -f | awk -F "." '{print $$2}'` \
	 && export found="no" \
	 &&  case $$HOSTNAME in \
	        ( frontera ) export found="yes" ;; \
	        ( stampede2 ) export found="yes" ;; \
	        ( ls5 ) export found="yes" ;; \
	         esac \
	 && if [ "$$found" = "no" ] ; then echo "Unknown host `hostname -f`" ; exit 1 ; fi \
	 && echo "generating script for ${EXECUTABLE} on $$HOSTNAME" \
	 && eval export CORES=$$[ ${CORESPERNODE}*${NODES} ] \
	 && eval export MINUTES=$$[ 2* ${COVERAGE} * ${TIME} / 60 ] \
	 && export QUEUE=`if [ $$CORES -le 256 ] ; then echo development ; else echo normal ; fi` \
	 && if [ ! -z "${SLURM_NNODES}" ] ; then \
	        echo "We are on a compute node: I am making a shell script" \
	         && template="shellscript_template" && generated="shellscript_generated" \
	    ; else \
	        echo "We are on the login node: I am making a batch script" \
	         && template="jobscript_template.$$HOSTNAME" && generated="jobscript_generated" \
	    ; fi \
	 && cat $${template} | sed -e "s/SSH/${SSH}/" -e "s/RUN/${RUN}/" \
	        -e "s/EXECUTABLE/${EXECUTABLE}/" -e "s/NODES/${NODES}/" \
	        -e "s/NAME/${NAME}/" \
	        -e "s/CORES/$$CORES/" -e "s/QUEUE/$$QUEUE/" \
	        -e "s/MINUTES/$$MINUTES/" \
	        > $${generated}
submit :
	sbatch jobscript_generated

example_shifted_ibrun_dependencies = parallel

CPROGRAMS = parallel randomaction randomsleep
info ::
	@echo 
	@echo "make PROGRAM"
	@echo "    with C programs: ${CPROGRAMS}"
	@echo "    compiled with WAIT=SLURM_NPROCS"
.SECONDEXPANSION:
parallel randomaction :
	@slurm=${SLURM_NPROCS} && slurm=$${slurm:=40} \
	&& wait=${WAIT} && wait=$${wait:=$${slurm}} \
	&& echo "compile $@ with wait=$$wait" \
	&& mpicc -o $@ $@.c -DWAIT=$${wait:=20}
randomsleep :
	mpicc -g -O2 -o $@ $@.c 
clean ::
	@rm -f ${CPROGRAMS}

info ::
	@echo 
	@echo "make unittests"
	@echo "  this submits a unittest run (nosetests pylauncher.py) to the queue"
unittests :
	@ln -s ../pylauncher.py pylauncher.py
	@make submit RUN=nosetests EXECUTABLE=pylauncher

##
## input files
##
info ::
	@echo
	@echo "make commandlines [COVERAGE=...] [ NCORES=...] [TIME=...] [COMMAND=...]"
	@echo "    number of jobs = COVERAGE * NCORES"
	@echo "    values: ${COVERAGE} ${NCORES}"
	@echo "make randomcommandlines : use"
	@echo "    COMMAND=\"mkdir -p random/PYL_ID && cd random/PYL_ID && ../../randomaction PYL_ID > random.out\""
NCORES = ${SLURM_NPROCS}
TIME = 20
TMIN = 0
COVERAGE = 4
COMMAND = sleep
.PHONY : commandlines
commandlines :
	@if [ -z "${NCORES}" ] ; then echo "Please set NCORES variable" && exit 1 ; fi
	@export number_of_jobs=$$[ ${COVERAGE} * ${NCORES} ] \
	&& echo "make $$number_of_jobs commandlines" \
	&& PYTHONPATH=../src/pylauncher:${PYTHONPATH} python3 make_commandlines.py \
	        "${COMMAND}" $$number_of_jobs \
	        `if [ "${TMIN}" = "0" ] ;   then echo 1 ; \
	         elif [ "${TMIN}" = "1" ] ; then echo ${TIME} ; \
	         else                            echo ${TMIN} ; fi` \
	        ${TIME}

.PHONY: randomcommandlines
randomcommandlines :
	@make --no-print-directory commandlines \
	    COVERAGE=${COVERAGE} NCORES=${NCORES} \
	    COMMAND="mkdir -p random/PYL_ID && cd random/PYL_ID && ../../randomaction PYL_ID > random.out"
clean ::
	@echo "clean random"
	@rm -rf random

##
## run
##
info ::
	@echo "make localrun EXAMPLE=..."
EXAMPLE = example_classic_launcher.py
.PHONY: localrun
localrun :
	@if [ ! -f "${EXAMPLE}" ] ; then \
	    echo "No such file: ${EXAMPLE}" && exit 1 ; fi 
	PYTHONPATH=../src:${PYTHONPATH} python3 ${EXAMPLE}
clean ::
	@echo "clean tmp dir"
	@/bin/rm -rf pylauncher_tmp*

##
## clean rules
##

info ::
	@echo 
	@echo "make clean"

clean ::
	@echo "clean simple files"
	@/bin/rm -f *.pyc *~ *.o *.log \
	      expire* sleepexpire* tmpdir* tasktest* dirtest queuestate* pytmp* \
	      jobscript_generated
	@echo "clean job output"
	@/bin/rm -rf pylauncher*.{e,o}[0-9]*
	@echo "clean test output"
	@/bin/rm -rf pylaunchertest*
