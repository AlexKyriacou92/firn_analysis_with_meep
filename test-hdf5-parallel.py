
import numpy as np
import h5py
from mpi4py import MPI

from simulation import flush_receiver_buffers

comm = MPI.COMM_WORLD
rank = comm.Get_rank()

fname = "test_hdf5_mpi.h5"

nRx = 3
n_buffer = 10

# All ranks use identical test data.
pulse_r_buffer = np.ones((nRx, n_buffer), dtype=np.complex128)
pulse_z_buffer = 2 * np.ones((nRx, n_buffer), dtype=np.complex128)

# Create the datasets collectively.
with h5py.File(fname, "w", driver="mpio", comm=comm) as f:
    f.create_dataset(
        "rxPulses_r",
        shape=(nRx, 0),
        maxshape=(nRx, None),
        chunks=(1, n_buffer),
        dtype=np.complex128,
    )
    f.create_dataset(
        "rxPulses_z",
        shape=(nRx, 0),
        maxshape=(nRx, None),
        chunks=(1, n_buffer),
        dtype=np.complex128,
    )

    comm.Barrier()

    print(f"Rank {rank}: flushing buffers", flush=True)

    flush_receiver_buffers(
        f["rxPulses_r"],
        f["rxPulses_z"],
        pulse_r_buffer,
        pulse_z_buffer,
        n_buffer,
    )

    print(f"Rank {rank}: flush complete", flush=True)

comm.Barrier()

# Verify after every rank has closed the parallel file.
if rank == 0:
    with h5py.File(fname, "r") as f:
        r = f["rxPulses_r"][:]
        z = f["rxPulses_z"][:]

        assert r.shape == (3, 10), r.shape
        assert z.shape == (3, 10), z.shape
        np.testing.assert_allclose(r, 1.0)
        np.testing.assert_allclose(z, 2.0)

    print("SUCCESS: MPI HDF5 buffer test passed!", flush=True)
