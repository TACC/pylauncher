#include <stdlib.h>
#include <stdio.h>
#include "unistd.h"
#include "mpi.h"

int main(int argc,char **argv) {
  int jobno,slp,mytid,ntids;
  MPI_Init(&argc,&argv);
  MPI_Comm_size(MPI_COMM_WORLD,&ntids);
  MPI_Comm_rank(MPI_COMM_WORLD,&mytid);
  if (argc<2) {
    if (mytid==0) printf("Usage: parallel id slp\n");
  }
  jobno = atoi(argv[1]);
  slp = atoi(argv[2]);
  if (mytid==0) {
    printf("Job %d on %d processors\n",jobno,ntids);
  }
  sleep(slp);
  MPI_Finalize();
  return 0;
}
