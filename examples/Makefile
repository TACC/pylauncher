info ::
	@echo "================================================================"
	@echo " This makefile tries to make it easy to run and submit example programs"
	@echo " supported clusters: stampede"
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
	    ( stampede ) export found="yes" ;; \
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
micsubmit :
	make ${${EXECUTABLE}_dependencies}
	echo "submitting ${EXECUTABLE}  on  MIC"
	export QUEUE=development ; \
	  cat jobscr.mic \
	      | sed \
	        -e "s/EXECUTABLE/${EXECUTABLE}/" -e "s/QUEUE/$$QUEUE/" \
	        > jobscr ; \
	  sbatch jobscr

parallel :
	mpicc -o $@ $@.c
clean ::
	@/bin/rm -f parallel

info ::
	@echo 
	@echo "make unittests"
	@echo "  this submits a unittest run (nosetests pylauncher.py) to the queue"
unittests :
	@ln -s ../pylauncher.py pylauncher.py
	@make submit RUN=nosetests EXECUTABLE=pylauncher

info ::
	@echo
	@echo "make commandlines [NODES=...] [TIME=...]"
#[COVERAGE=... (default=${COVERAGE})]"
NODES = 2
TIME = 20
COVERAGE = 4
CORESPERNODE = 16
.PHONY : commandlines
commandlines :
	export number_of_jobs=$$[ ${COVERAGE} * ${NODES} * ${CORESPERNODE} ] ; \
	PYTHONPATH=..:${PYTHONPATH} python make_commandlines.py $$number_of_jobs 1 $$[ 2*${TIME} ]

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
