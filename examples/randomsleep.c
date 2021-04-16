/****************************************************************
 *
 * This example program is part of the pylauncher distribution
 * copyright Victor Eijkhout 2020
 *
 * Usage: randomsleep t [ tmax ]
 * -- if tmax not given: random sleep up to `t' seconds
 * -- if tmax given    : random sleep time in [t,tmax] interval
 *
 ****************************************************************/

#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

int main(int argc,char **argv) {
  srand(time(NULL));

  int tmin,tmax;

  switch (argc) {
  case 1 : 
    printf("Usage: randomaction t [ tmax ]\n"); 
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
  sleep(nseconds);
  printf("There. I did it.\n");
  return 0;
}
