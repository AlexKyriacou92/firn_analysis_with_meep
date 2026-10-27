#!/bin/sh
#SBATCH --job-name=example_job
#SBATCH --partition=serial
#SBATCH --time=0-1:0:0
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --cpus-per-task=1
#SBATCH --account=PAS1968
#SBATCH --mail-user=alexander.luke.kyriacou@ulb.be
#SBATCH --mem-per-cpu=2000 # in MB
#SBATCH -o example_job.out
mpirun -n 8 python run-sim-parallel.py config-in.txt