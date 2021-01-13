/****************************************************************
 *
 * This example program is part of the pylauncher distribution
 * copyright Victor Eijkhout 2020
 *
 * Usage: sleep n
 *
 ****************************************************************/

#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

#ifndef WAIT
#define WAIT 10
#endif

int main(int argc,char **argv) {
  srand(time(NULL));

  /* 
   * random duration under argv[1]
   * but max 30
   */
  int nseconds = atoi(argv[1]);
  if (nseconds>WAIT) nseconds = WAIT;
  nseconds = rand() % nseconds;

  printf("I am going to sleep for %d seconds\n",nseconds);
  sleep(nseconds);
  printf("There. I did it.\n");
  return 0;
}
