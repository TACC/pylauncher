/****************************************************************
 *
 * This example program is part of the pylauncher distribution
 * copyright Victor Eijkhout 2024
 *
 ****************************************************************/

#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include <omp.h>

int main(int argc,char **argv) {
  srand(time(NULL));

  int tmin=20,tmax=30;

  int nseconds;
  if (tmin==tmax)
    nseconds = tmin;
  else 
    nseconds = tmin + rand() % (tmax-tmin);

  printf("Detected core count: %d\n",omp_get_num_procs());
  printf("I am going to sleep for %d seconds\n",nseconds);
  sleep(nseconds);
  printf("There. I did it.\n");
  return 0;
}
