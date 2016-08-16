#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc,char **argv) {
  int random_num,rand_max;

  rand_max = atoi(argv[1]);
  random_num = (int) ( (rand() / (double)RAND_MAX) * rand_max );
  random_num = random_num%20;
  printf("Random number under %d: %d\n",rand_max,random_num);
  sleep(random_num);
  
  return 0;
}

