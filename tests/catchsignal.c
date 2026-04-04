#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static void on_sigusr1(int sig)
{
  fprintf(stderr,"SIGUSR1 caught\n");
}

int main(void)
{
  fprintf(stderr,"Start waiting for SIGUSR1 \n");

  struct sigaction sa = {0};
  sa.sa_handler = on_sigusr1;
  sigemptyset(&sa.sa_mask);
  sa.sa_flags = 0;

  if (sigaction(SIGUSR1, &sa, NULL) == -1) {
    perror("sigaction");
    return EXIT_FAILURE;
  }

  pause(); /* wait for any signal */
  return EXIT_SUCCESS;
}
