
# Firn Analysis with Meep

This repository contains Python code for simulating radio-wave propagation through polar ice and firn using the finite-difference time-domain (FDTD) solver [Meep](https://meep.readthedocs.io/).

The simulations use a two-dimensional cylindrical geometry with a depth-dependent refractive-index profile. A radio pulse is emitted from a source within the ice, and the electric fields are recorded at specified receiver positions.

The code supports parallel simulations using MPI, with receiver waveforms written to HDF5 files using buffered output.

## Installation

The code requires Python, Meep, NumPy, SciPy, h5py, and mpi4py.

See [Installation.md](Installation.md) for detailed instructions on installing parallel Meep on the Ohio Supercomputer Center (OSC) Cardinal cluster.

## Cluster Settings
Before running a simulation (see below), you need to edit the cluster settings in: config-cluster.txt
If running on OSC, you need to have a project account to use the resources, defined here:
`ACCOUNT = PASxxx`
You need to edit this to the project account that you are using.
Also change:
`MAIL = myemail.edu` to your email
You will need to check what partitions are available and appropriate for your application:
i.e. `PARTITION = cpu`

If running on a different cluster, the ACCOUNT and MAIL lines can probably be removed - but this will depend on the cluster

## Running a simulation

Simulation parameters, including the geometry, source pulse, refractive-index profile, receiver positions, and output settings, are specified in a configuration file.

An example is provided in `config-example.txt`.

To run a simulation in parallel you can run:
```bash
mpirun -n 4 python run-sim-parallel.py config-example.txt
```
The number of MPI processes should be adjusted according to the available computational resources.

If running on a cluster you will first need to create a sh script (i.e. ```test-job.sh```, and submit it to the cluster with SLURM:
You can do this using ```create_job.py```
```
python create_job.py config.cluster.txt <submit_int> <override_int>
```

The latter two arguments:
- submit_int = 0 just creates the shell script, while submit_int = 1 creates and submits it with sbatch. I recommend settings this to its default of 0
- override_int = 0 means that if a shell script of the same name already exists, you will create a new one with a number appended to it, i.e. test-job-1.sh. override_int = 1 will over-write the exisitng shell script

Your shell script should look something like this:
```
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
```

Finally you submit the job to cluster using:

```
sbatch test-job.sh
```

The simulation on config-example.txt, using 26 cores on cluster (2 GB) each should take around 2-3 hours to complete


## Code structure

#### Run Simulations Scripts:
- `run-sim-parallel.py` - Main script for running parallel Meep simulations.
- `run-sim-one.py` - Script for running a simulation without MPI.

These are controlled using two config files
- `config-example.txt` - defines the simulation properties, including the geometry, positions of the source ande receiver and the source signal properties
- `config-cluster.txt` - defines the job submitted to cluster, including number of nodes, cpus, memory per cpu, max time

#### Simulation Definition and Utility Scripts:
- `simulation.py` - Simulation configuration, geometry, source definition, and HDF5 output routines.
- `reader.py` — Reading and processing simulation output.
- `util.py` — Utility functions, including signal processing.
- `cluster.py` - Cluster job utilities.
- `create_job.py` - creates sh script 

#### Plotting and Analysis Scripts
- `plot-pulses.ipynb` - example of how to read data and generate basic plots, i.e. the geomtery, the source ande receiver waveforms

#### Other
- 'example-job.sh' - an example shell script

## Output
Simulation results are saved in HDF5 format, including the source waveform, receiver positions, refractive-index profile, and recorded radial and vertical electric-field components.

## Status
This code is under active development. I will be updating the documentation over time.
Users should independently validate simulation results for their intended applications.
For any issues: please contact me at alexander.luke.kyriacou@ulb.be