#!/bin/sh
#SBATCH --job-name=test_job
#SBATCH --partition=cpu
#SBATCH --time=0-1:0:0
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --cpus-per-task=1
#SBATCH --account=PASxxxxx
#SBATCH --mail-user=myemail.edu
#SBATCH --mem-per-cpu=2000 # in MB
#SBATCH -o test_job.out
mpirun -n 8 python run-sim-parallel.py config-in.txt