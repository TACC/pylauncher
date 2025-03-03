#!/bin/bash

# submission line for frontera RTX gpus
make totalclean 
make gpusleep
make script submit QUEUE=rtx-dev EXECUTABLE=example_gpu_launcher NODES=2 CORESPERNODE=3
