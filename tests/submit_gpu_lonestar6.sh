#!/bin/bash

# submission line for Lonestar6 A100 gpus
make script submit QUEUE=gpu-a100 EXECUTABLE=example_gpu_launcher NODES=2 GPUSPERNODE=3
