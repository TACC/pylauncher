/****************************************************************
 *
 * This example program is part of the pylauncher distribution
 * copyright Victor Eijkhout 2020
 *
 * Usage: randomcomma tmin,tmax
 *
 ****************************************************************/

#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

int main(int argc,char **argv) {
  srand(time(NULL));

  int tmin=0,tmax=0;

  switch (argc) {
  case 1 : 
    printf("Usage: randomaction tmin,tmax\n"); 
    return 0;
  case 2 : 
    sscanf(argv[1],"%d,%d",&tmin,&tmax);
    break;
  default:
    printf("Usage: randomaction tmin,tmax\n"); 
    return 0;
  }

  printf("Found tmin=%d tmax=%d\n",tmin,tmax);
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
