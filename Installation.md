## Overview

This guide describes how to install and run **parallel Meep** on the Ohio Supercomputer Center (OSC) Cardinal cluster using precompiled packages from Conda Forge.

The installation was successfully tested on **21 October 2026**.

The resulting environment includes:

- Meep 1.35.0
    
- MPI-enabled Meep using MPICH
    
- Parallel HDF5
    
- Python 3.12
    
- MPI4Py
    

This approach avoids manually compiling Meep, HDF5, FFTW, and their dependencies.

**Important:** The Conda installation is independent of any existing Meep installation. There is no need to delete older installations before proceeding.

---

## 1. Connect to OSC Cardinal

Connect to Cardinal using SSH:

```
ssh akyriacou92@cardinal.osc.edu
```

The following steps initially take place on a login node. Actual Meep simulations should be run on compute nodes.

## 2. Prepare the module environment

OSC loads compiler and MPI modules by default. These may conflict with the MPI libraries installed by Conda.

If OpenMPI and Intel oneAPI modules are loaded, unload them:

```
module unload openmpi
module unload oneapi
module unload intel-oneapi-mkl
```

If MVAPICH or Intel compiler modules are loaded instead, unload those as appropriate:

```
module unload mvapich
module unload intel
```

Check the remaining modules:

```
module list
```

It is not necessary to purge every module. The goal is to avoid conflicting MPI implementations and libraries.

## 3. Create the parallel Meep Conda environment

Create a new environment using Conda Forge:

```
conda create -n meep-parallel \
    -c conda-forge --strict-channel-priority \
    python=3.12 \
    "pymeep=*=mpi_mpich_*" \
    "h5py=*=mpi_mpich_*" \
    mpi4py
```

The `mpi_mpich_*` package constraints are important. They explicitly select MPI-enabled builds rather than serial (`nompi`) versions.

Activate the environment:

```
conda activate meep-parallel
```

Check that Python and MPI come from the environment:

```
which python
which mpiexec
```

On this OSC account, the expected paths are:

```
~/.conda/envs/meep-parallel/bin/python
~/.conda/envs/meep-parallel/bin/mpiexec
```

## 4. Check for an obsolete PYTHONPATH

This step is especially important if Meep was previously installed manually.

Check:

```
echo "$PYTHONPATH"
```

In the original setup, this returned:

```
~/.conda/envs/local/bin/python:/users/PAS1968/akyriacou92/software/meep-1.28.0/python
```

The second entry caused Python to import the old Meep 1.28.0 source file rather than the new Conda package.

This produced the error:

```
ModuleNotFoundError: No module named '_meep'
```

To remove this conflict temporarily:

```
unset PYTHONPATH
```

To fix it permanently, find where `PYTHONPATH` is defined:

```
grep -n 'PYTHONPATH' ~/.bashrc ~/.bash_profile ~/.profile 2>/dev/null
```

Edit the relevant startup file and comment out the obsolete Meep path assignment.

For example:

```
nano ~/.bashrc
```

An empty `PYTHONPATH` is acceptable. Conda automatically configures Python to find packages installed in its environment.

Do not confuse `PYTHONPATH` with the ordinary `PATH` variable.

## 5. Verify Meep and parallel HDF5

With the Conda environment activated, run:

```
python -c "import meep as mp; print('Meep version:', mp.__version__); print('Location:', mp.__file__)"
```

Successful output on OSC:

```
Using MPI version 4.1, 1 processes
Meep version: 1.35.0
Location: /users/PAS1968/akyriacou92/.conda/envs/meep-parallel/lib/python3.12/site-packages/meep/__init__.py
```

Then verify parallel HDF5:

```
python -c "import h5py; print('Parallel HDF5:', h5py.get_config().mpi)"
```

Expected output:

```
Parallel HDF5: True
```

You can also inspect the installed package variants:

```
conda list | grep -Ei 'meep|mpi|hdf5|h5py|fftw|mpb'
```

Check that the relevant packages use `mpi_mpich` builds rather than `nompi` builds.

## 6. Create a parallel Meep test

Create a file called `test_parallel_meep.py`:

```
from mpi4py import MPI
import meep as mp

comm = MPI.COMM_WORLD

print(f"MPI rank {comm.rank} of {comm.size}", flush=True)

sim = mp.Simulation(
    cell_size=mp.Vector3(4, 4, 0),
    resolution=10,
    sources=[],
)

sim.init_sim()

if mp.am_master():
    print("Parallel Meep initialized successfully!")
```

This creates a minimal simulation and initializes Meep across multiple MPI processes.

## 7. Request an interactive compute node

Meep simulations should run on compute nodes, not login nodes.

For a short interactive test, request a Slurm allocation:

```
salloc -A PAS2608 -p debug -N 1 -n 4 -t 00:30:00
```

This requests:

- Account: `PAS2608`
    
- Partition: `debug`
    
- Nodes: 1
    
- Tasks: 4
    
- Maximum duration: 30 minutes
    

Enter the allocated compute node:

```
srun --pty bash
```

Check the hostname:

```
hostname
```

Activate the environment if necessary:

```
conda activate meep-parallel
```

If the old Python path is still defined:

```
unset PYTHONPATH
```

## 8. Test parallel Meep execution

Run:

```
mpiexec -n 4 python test_parallel_meep.py
```

The test should report four MPI ranks and successful Meep initialization.

**This test was successfully completed on OSC Cardinal.**

It confirms that the new environment can initialize Meep using four MPI processes on a compute node.

Note that this is a basic functionality test. Larger production simulations should still be checked for performance, memory requirements, and scaling.

## 9. Running future simulations

For subsequent sessions, activate the environment:

```
conda activate meep-parallel
```

Run simulations within an appropriate Slurm allocation:

```
mpiexec -n 4 python simulation.py
```

Replace `4` with the number of MPI processes allocated to the job.

For longer simulations, use an `sbatch` script rather than an interactive session. Ensure that the script activates the Conda environment and does not load a conflicting MPI implementation.

## 10. Troubleshooting

### Python imports an old Meep version

Check:

```
python -c "import meep; print(meep.__file__)"
```

If it points to an old source directory, inspect `PYTHONPATH`:

```
echo "$PYTHONPATH"
```

Temporarily clear it:

```
unset PYTHONPATH
```

### ModuleNotFoundError: No module named '_meep'

In this installation, the error was caused by Python finding an old `meep.py` source file rather than the new Conda package.

Removing the obsolete `PYTHONPATH` entry resolved the issue.

### Meep is installed but runs without MPI

Check the package build:

```
conda list pymeep
```

The build should contain `mpi_mpich`, not `nompi`.

Also check:

```
which mpiexec
```

It should point to the Conda environment.

### Parallel HDF5 is disabled

Check:

```
python -c "import h5py; print(h5py.get_config().mpi)"
```

If it returns `False`, verify that the installed h5py package is an MPI-enabled build.

### MPI conflicts

Avoid mixing OpenMPI, MVAPICH, and MPICH within the same runtime environment.

For this installation, Meep and its dependencies were installed using the MPICH variants provided by Conda Forge.

## 11. Existing manual Meep installation

An older manually compiled Meep 1.28.0 source tree exists at:

```
~/software/meep-1.28.0/
```

Its original installation prefix was:

```
~/install/
```

That build was configured using OpenMPI 4.1.6 and Intel oneAPI 2024.1.0.

The new Conda environment does not depend on this older build.

**Do not delete** `**~/install**` **indiscriminately**, as it contains separately compiled HDF5 libraries and potentially other dependencies.

The older installation can be reviewed and cleaned up separately once it is no longer needed.

---

## Quick reference

For a new OSC session:

```
# Activate the environment
conda activate meep-parallel

# Only needed if an obsolete PYTHONPATH remains
unset PYTHONPATH

# Verify the installation
python -c "import meep as mp; print(mp.__version__)"

# Run inside a suitable Slurm compute allocation
mpiexec -n 4 python simulation.py
```

**Final status:** Parallel Meep 1.35.0 successfully installed and tested on OSC Cardinal, October 2026.