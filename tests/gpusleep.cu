// -*- c++ -*-
/****************************************************************
 *
 * This example program is part of the pylauncher distribution
 * copyright Victor Eijkhout 2020
 *
 * Usage: gpusleep t [ tmax ]
 * -- if tmax not given: random sleep up to `t' seconds
 * -- if tmax given    : random sleep time in [t,tmax] interval
 *
 ****************************************************************/

#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

// Kernel function to print "Hello, World!"
// __host__ __device__
__global__
 void helloWorldKernel() {
#if defined(__CUDA_ARCH__)
    printf("Hello from device\n");
#else
    printf("Hello from host\n");
#endif
};

// __global__ void helloWorldKernel() {
//   printf("Hello, World!\n");
// }

int main(int argc,char **argv) {
  srand(time(NULL));

  int tmin,tmax;

  switch (argc) {
  case 1 : 
    printf("Usage: randomaction t [ tmax ]\n"); 
    tmin = 4; tmax = 6;
    break;
  case 2 : 
    tmin = atoi(argv[1]); tmax = tmin;
    break;
  case 3 : 
    tmin = atoi(argv[1]); tmax = atoi(argv[2]);
    break;
  default:
    printf("Usage: randomaction t [ tmax ]\n"); 
    break;
  }

  int nseconds;
  if (tmin==tmax)
    nseconds = tmin;
  else 
    nseconds = tmin + rand() % (tmax-tmin);

  printf("I am going to sleep for %d seconds\n",nseconds);
//  helloWorldKernel();
  helloWorldKernel<<<1, 1>>>();
  // Wait for the GPU to finish executing the kernel
  cudaDeviceSynchronize();
  sleep(nseconds);
  printf(" .. done kernel and back\n");

  return 0;
}
