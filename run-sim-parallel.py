import datetime
import numpy as np
import math
import h5py
import sys
import configparser
from mpi4py import MPI
import meep as mp
import os
import time
#from functools import partial

from simulation import set_simulation_cylinder, sim_settings, create_simulation_output, flush_receiver_buffers
from simulation import get_amp_at_t
from util import add_data_to_hdf

print('Initiating Simulation of a pulse generated from a point source inside a modelled ice-sheet (range-independent)')
def main(fname_config, comm):
    sim_settings_in = sim_settings(fname_config=fname_config)
    sim_dipole, rxList_meep = set_simulation_cylinder(sim_settings_in=sim_settings_in)
    path2sim = sim_settings_in.path2sim
    os.makedirs(path2sim, exist_ok=True)
    fname_out = path2sim + '/' + sim_settings_in.fname_prefix + '_z_tx_' + str(sim_settings_in.sourceDepth) + '_buffer.h5'
    print(f"Rank {comm.rank}: before HDF5 creation", flush=True)
    create_simulation_output(fname_out, settings=sim_settings_in, parallel_mode=True, comm=comm)
    print(f"Rank {comm.rank}: after HDF5 creation", flush=True)
    n_buffer = sim_settings_in.n_buffer
    nRx = sim_settings_in.nRx

    pulse_r_buffer = np.zeros((nRx, n_buffer), dtype=np.complex128)
    pulse_z_buffer = np.zeros((nRx, n_buffer), dtype=np.complex128)

    # Buffer state tracker
    state = {"buffer_index": 0,"step_index": 0}
    dt_C = sim_settings_in.dt_C
    decimation_factor = sim_settings_in.decimation_factor
    t_end_meep = sim_settings_in.t_end_meep

    print(f"Rank {comm.rank}: entering init_sim()", flush=True)
    print("cell_size:", sim_dipole.cell_size)
    print("resolution:", sim_dipole.resolution)
    print("dimensions:", sim_dipole.dimensions)
    print("geometry:", sim_dipole.geometry)
    print("boundary_layers:", sim_dipole.boundary_layers)

    with h5py.File(fname_out, 'r+', driver='mpio', comm=comm) as output_hdf:
        print(f"Rank {comm.rank}: after HDF5 open", flush=True)

        pulse_r_ds = output_hdf["rxPulses_r"]
        pulse_z_ds = output_hdf["rxPulses_z"]
        '''
        receiver_callback = partial(
            get_amp_at_t,
            rxList_meep=rxList_meep,
            pulse_r_buffer=pulse_r_buffer,
            pulse_z_buffer=pulse_z_buffer,
            state=state,
            pulse_r_ds=pulse_r_ds,
            pulse_z_ds=pulse_z_ds
        )
        
        def receiver_callback(sim, rxList_meep=rxList_meep,
                              pulse_r_buffer=pulse_r_buffer, pulse_z_buffer=pulse_z_buffer,
                              state=state, pulse_r_ds=pulse_r_ds, pulse_z_ds=pulse_z_ds):
            return get_amp_at_t(sim, rxList_meep, pulse_r_buffer, pulse_z_buffer, state, pulse_r_ds, pulse_z_ds)
        '''

        def get_amp_at_t2(sim):
            nonlocal pulse_r_buffer, pulse_z_buffer, state
            idx = state["buffer_index"]
            # Sample Meep fields
            for i, rx_pt in enumerate(rxList_meep):
                pulse_r_buffer[i, idx] = sim.get_field_point(mp.Ex, rx_pt)
                pulse_z_buffer[i, idx] = sim.get_field_point(mp.Ez, rx_pt)

            state["buffer_index"] += 1
            state["step_index"] += 1

            # Write when the buffer is full
            if state["buffer_index"] == pulse_r_buffer.shape[1]:
                flush_receiver_buffers(
                    pulse_r_ds,
                    pulse_z_ds,
                    pulse_r_buffer,
                    pulse_z_buffer,
                    state["buffer_index"]
                )
                state["buffer_index"] = 0

        #Initialize Simulation

        print('Initialize Simulation')
        tstart_initial = time.time()
        '''        
        with open(f"/tmp/meep_rank_{comm.rank}.log", "w") as f:
            f.write("Entering init_sim\n")
            f.flush()
        '''
        sim_dipole.init_sim()
        print(
            f"Rank {comm.rank}: finished init_sim()",
            flush=True
        )
        tend_initial = time.time()

        now = datetime.datetime.now()

        duration = tend_initial-tstart_initial

        print('Simulation Initialization Complete')
        print('Duration: ', datetime.timedelta(seconds=duration))
        print('')

        # Set Output Directory
        sim_dipole.use_output_directory(path2sim)

        print('Simulation run starting at: ', now)
        print('')

        tstart_run = time.time()

        # Running the Simulation with decimation
        #sim_dipole.run(mp.at_every(dt_C * decimation_factor, receiver_callback), until=t_end_meep)
        sim_dipole.run(mp.at_every(dt_C * decimation_factor, get_amp_at_t2), until=t_end_meep)

        # ========== Final flush for leftover buffer ==========
        if state["buffer_index"] > 0:
            print('Final flush: writing remaining ', state["buffer_index"], 'steps...')
            flush_receiver_buffers(pulse_r_ds, pulse_z_ds, pulse_r_buffer, pulse_z_buffer, state["buffer_index"])

        #output_hdf.close()
        print('')
        tend_run = time.time()
        now = datetime.datetime.now()
        duration = tend_run - tstart_run
        print('Simulation Run Complete at', now)
        print('Duration: ', datetime.timedelta(seconds=duration))
    print('Data saved to ', fname_out)

if __name__ == "__main__":
    if len(sys.argv) == 2:
        fname_config = sys.argv[1]
    else:
        fname_config = 'config-example.txt'
    comm = MPI.COMM_WORLD
    main(fname_config=fname_config, comm=comm)