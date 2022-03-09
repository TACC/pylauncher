/****************************************************************
 *
 * This example program is part of the pylauncher distribution
 * copyright Victor Eijkhout 2020
 *
 ****************************************************************/

#include <stdlib.h>
#include <stdio.h>
#include "unistd.h"
#include "mpi.h"

int main(int argc,char **argv) {
  int jobno,slp,mytid,ntids;
  char outfile[5+5+5+1]; 
  FILE *f;

  MPI_Init(&argc,&argv);
  MPI_Comm_size(MPI_COMM_WORLD,&ntids);
  MPI_Comm_rank(MPI_COMM_WORLD,&mytid);
  if (argc<2) {
    if (mytid==0) printf("Usage: parallel id slp\n");
  }
  jobno = atoi(argv[1]);
  slp = atoi(argv[2]);

  int namelen = MPI_MAX_PROCESSOR_NAME;
  char procname[MPI_MAX_PROCESSOR_NAME];
  MPI_Get_processor_name(procname,&namelen);

  MPI_Barrier(MPI_COMM_WORLD);
  /* sprintf(outfile,"pytmp-%04d-%04d",jobno,mytid); */
  /* f = fopen(outfile,"w"); */
  /* fprintf(f,"on host %s\n",procname); */
  /* fprintf(f,"%d/%d working\n",mytid,ntids); */
  /* fclose(f); */

  if (mytid==0) {
    printf("Job %d on %d processors\n",jobno,ntids);
  }
  sleep(slp);
  MPI_Finalize();
  return 0;
}
