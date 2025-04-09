#!/bin/bash

#
# default examples
# note: submit needs to come last!
#

function usage () {
    echo "Usage: $0 [ -h ] [ -e ex1,ex2,ex3,... ]"
    echo " where examples: ${examples}"
}

recompile=1
examples="classic comma core filecore ibrun fileibrun node gpu submit"
while [ $# -gt 0 ] ; do
    if [ "$1" = "-h" ] ; then
	usage && exit 0
    elif [ "$1" = "-e" ] ; then
	shift && examples=$1 && recompile=0 && shift
    else
	echo "Unknown option: $1" && exit 1
    fi
done

QUEUE_frontera=normal
QUEUE_ls6=normal
QUEUE_stampede3=skx
QUEUE_vista=gg
export cores_per_node=$(
    case ${TACC_SYSTEM} in \
	( vista ) echo 112 ;;
	( frontera )  echo 56 ;;
	( ls6 ) echo 128 ;;
	( stampede3 ) echo 48 ;;
    esac )
echo "Using ${cores_per_node} cores per node"

if [ $recompile -eq 1 ] ; then
    make totalclean
    if [ $? -gt 0 ] ; then echo 1 ; fi
    make programs
    if [ $? -gt 0 ] ; then echo 1 ; fi
fi

# 
# Example loop
#
eval QUEUE=\${QUEUE_${TACC_SYSTEM}}
echo "QUEUE = ${QUEUE}"
for e in \
        $( echo ${examples} | tr ',' ' ' ) \
	; do
    echo "Running example: $e"
    if [ $e = "submit" ] ; then
	python3 example_submit_launcher.py 2>&1 | tee -a pylaunchertestsubmit.o000
    elif [ $e = "gpu" ] ; then
	case ${TACC_SYSTEM} in \
	    ( vista )
            make --no-print-directory script submit \
		 NAME=gpu EXECUTABLE=gpu QUEUE=gh
	    ;;
	    ( frontera ) 
            make --no-print-directory script submit \
		 NAME=gpu EXECUTABLE=gpu QUEUE=rtx
	    ;;
	    ( ls6 ) 
            make --no-print-directory script submit \
		 NAME=gpu EXECUTABLE=gpu QUEUE=a100
	    ;;
	    ( * ) echo "No GPUs on system ${TACC_SYSTEM} to test" ;;
	esac
    else
	make --no-print-directory script submit \
	     NAME=${e} \
	     QUEUE=${QUEUE} \
	     CORESPERNODE=${cores_per_node} \
	     EXECUTABLE=${e}
    fi
done

