import datetime
import numpy as np
import math
import h5py
import sys
import configparser
import meep as mp
import os
import time
from util import butterBandpassFilter, get_data, findNearest
from util import nice, c_mGHz, nair

import os
import configparser
import numpy as np

class sim_settings:
    """
    Configuration and derived parameters for a Meep simulation.
    Reads a configuration file and initializes geometry, source,
    receiver, and refractive-index parameters.
    All time parameters ending in _ns are in nanoseconds.
    Meep time parameters use Meep's internal units [meters].
    """
    def __init__(self, fname_config, fname_hdf=None):
        if (fname_config is None) and (fname_hdf is None):
            raise ValueError("Supply exactly one of fname_config or fname_hdf")
        self.config = None
        if fname_config is not None:
            config_file = os.path.join(os.path.dirname(__file__), fname_config)
            self.config = configparser.ConfigParser()
            if not self.config.read(config_file):
                raise FileNotFoundError(f"Could not read configuration file: {config_file}")
            self.set_general_from_config()
            self.set_geometry_from_config()
            self.set_source_from_config()
            self.set_receivers_from_config()
            self.set_ref_index_from_config()
        else:
            self.set_from_hdf(fname_hdf)

    def set_from_hdf(self, fname_hdf):
        """Restore settings from an output produced by create_simulation_output."""
        with h5py.File(fname_hdf, "r") as f:
            attrs = f.attrs
            self.iceDepth = float(attrs["iceDepth"])
            self.iceRange = float(attrs["iceRange"])
            self.airHeight = float(attrs["airHeight"])
            self.boreholeRadius = float(attrs["boreholeRadius"])
            self.pad = float(attrs["pad"])
            self.resolution = float(attrs["res"])
            self.absorb_mode = int(attrs["absorb_mode"])
            self.sourceDepth = float(attrs["sourceDepth"])
            self.sourceRange = float(attrs["sourceRange"])
            self.decimation_factor = float(attrs["decimation_factor"])
            self.n_buffer = int(attrs["n_buffer"])

            self.dt_meep = float(attrs["dt_meep"])
            self.dt_ns = float(attrs["dt_ns_res"])
            self.dt_ns_deci = float(attrs["dt"])
            self.dt_C = self.dt_meep
            self.mpp = 1.0 / self.resolution
            self.S_courant = float(attrs.get("S_courant", self.dt_meep * self.resolution))

            # Legacy files did not record rangeBuffer or cutoff_factor.
            # Defaults below reproduce the configuration defaults, but may
            # differ from a legacy run that explicitly overrode them.
            self.rangeBuffer = float(attrs.get("rangeBuffer", self.pad))
            self.cutoff_factor = float(attrs.get("cutoff_factor", 1.1))
            self.t_end_meep = float(attrs.get("t_end_meep", self.cutoff_factor * nice * self.iceRange))
            self.t_end_ns = self.t_end_meep / c_mGHz
            self.nSteps = int(self.t_end_meep / self.dt_meep)

            self.pulse_in = f["txPulse"][:]
            self.tspace_in = f["tspace_tx"][:]
            self.tspace_meep = self.tspace_in * c_mGHz
            self.nSamples_in = len(self.pulse_in)
            self.rxList = np.atleast_2d(f["rxList"][:])
            if self.rxList.shape[1] != 2:
                raise ValueError("Receiver positions must have shape (nRx, 2)")
            self.nRx = len(self.rxList)
            self.zprof_in = f["zProfile"][:]
            self.nprof_in = f["nProfile"][:]

            # Saved arrays suffice to reproduce the original material profile.
            # The original analytic/data model cannot be inferred from old files.
            self.ref_index_data_mode = "data"
            self.signal_mode = "data"
            self.rx_data_defined = True
            self.path2sim = os.path.dirname(os.path.abspath(fname_hdf))
            self.fname_prefix = str(attrs.get("prefix", os.path.basename(fname_hdf).removesuffix(".h5")))

    def set_general_from_config(self):
        settings = self.config["SETTINGS"]
        self.path2sim = settings["path2output"]
        self.fname_prefix = settings["prefix"]

    def set_geometry_from_config(self):
        geometry = self.config["GEOMETRY"]
        settings = self.config["SETTINGS"]

        # Geometry
        self.iceDepth = geometry.getfloat("iceDepth")
        self.iceRange = geometry.getfloat("iceRange")
        self.airHeight = geometry.getfloat("airHeight")
        self.boreholeRadius = geometry.getfloat("boreholeRadius")
        self.pad = geometry.getfloat("pad")
        self.resolution = geometry.getfloat("resolution")

        self.rangeBuffer = geometry.getfloat( "rangeBuffer", fallback=self.pad )
        self.absorb_mode = geometry.getint("absorb_mode", fallback=0)

        # Numerical parameters
        self.S_courant = settings.getfloat("S_courant")
        if self.resolution <= 0:
            raise ValueError("resolution must be positive")

        self.mpp = 1.0 / self.resolution
        self.dt_meep = self.S_courant * self.mpp
        self.dt_ns = self.dt_meep / c_mGHz
        self.dt_C = self.dt_meep

    def set_source_from_config(self):
        source = self.config["SOURCE"]
        self.sourceDepth = source.getfloat("sourceDepth")
        self.sourceRange = source.getfloat("sourceRange")

        self.signal_mode = source["mode"].strip().lower()
        if self.signal_mode == "impulse":
            self.t_end_in = source.getfloat("stopTime")
            self.t_center = source.getfloat("startTime")
            self.freq_LP = source.getfloat("freq_LP")
            self.freq_HP = source.getfloat("freq_HP")
            self.order = source.getint("order")
            self.nSamples_in = int(self.t_end_in / self.dt_ns)
            if self.nSamples_in < 1:
                raise ValueError(
                    "Source pulse window must contain at least one sample"
                )
            self.tspace_in = (
                np.arange(self.nSamples_in) * self.dt_ns
            )
            self.tspace_meep = (
                np.arange(self.nSamples_in) * self.dt_meep
            )
            self.impulse = np.zeros(self.nSamples_in)
            ii_cent = findNearest(self.tspace_in, self.t_center)
            self.impulse[ii_cent] = 1.0
            self.pulse_in = butterBandpassFilter(self.impulse,self.freq_HP,self.freq_LP,1.0 / self.dt_ns,self.order)

        elif self.signal_mode == "data":
            self.fname_source = source["sourceFile"]
            self.pulse_in, self.tspace_in = get_data( self.fname_source)
            self.nSamples_in = len(self.tspace_in)
            self.tspace_meep = self.tspace_in * c_mGHz
            self.nSamples_in = len(self.pulse_in)
        else:
            raise ValueError(
                f"Unknown source mode: {self.signal_mode}. "
                "Expected 'impulse' or 'data'."
            )

    def set_receivers_from_config(self):
        receiver = self.config["RECEIVER"]
        # Sampling and simulation duration
        self.decimation_factor = receiver.getfloat("decimation_factor", fallback=1.0)
        self.cutoff_factor = receiver.getfloat("cutoff_factor", fallback=1.1)
        self.t_end_meep = ( self.cutoff_factor * nice * self.iceRange )
        self.t_end_ns = self.t_end_meep / c_mGHz

        self.nSteps = int(self.t_end_meep / self.dt_meep )

        self.dt_ns_deci = (self.dt_ns * self.decimation_factor)
        # Receiver buffer
        self.n_buffer = receiver.getint("n_buffer", fallback=1000)
        if self.n_buffer <= 0:
            raise ValueError("n_buffer must be positive")

        # Receiver positions
        self.rx_data_defined = receiver.getboolean( "data_defined", fallback=False)

        if self.rx_data_defined:
            self.fname_rx_list = receiver["rx_list"]
            self.rxList = np.genfromtxt(self.fname_rx_list )
        else:
            rx_x_min = receiver.getfloat("rx_x_min")
            rx_x_max = receiver.getfloat("rx_x_max")
            rx_dx = receiver.getfloat("rx_dx")
            rx_z_min = receiver.getfloat("rx_z_min")
            rx_z_max = receiver.getfloat("rx_z_max")
            rx_dz = receiver.getfloat("rx_dz")
            rx_x_l = np.arange(rx_x_min, rx_x_max + rx_dx, rx_dx)

            rx_z_l = np.arange(rx_z_min, rx_z_max + rx_dz, rx_dz)
            self.rxList = np.array([
                [rx_x, rx_z]
                for rx_x in rx_x_l
                for rx_z in rx_z_l
            ])

        self.rxList = np.atleast_2d(self.rxList)
        if self.rxList.shape[1] != 2:
            raise ValueError("Receiver positions must have shape (nRx, 2)")

        self.nRx = len(self.rxList)

    def set_ref_index_from_config(self):
        ref_index = self.config["REFRACTIVE INDEX"]
        self.ref_index_data_mode = (ref_index["mode"].strip().lower())
        if self.ref_index_data_mode == "data":
            self.ref_index_data_file = ref_index["data_file"]
            self.nprof_in, self.zprof_in = get_data(self.ref_index_data_file)

        elif self.ref_index_data_mode == "1exp":
            self.n_ice = ref_index.getfloat("n_ice")
            self.n_surf = ref_index.getfloat("n_surf")
            self.k_ref = ref_index.getfloat("k_ref")
            dz = 0.05
            self.zprof_in = np.arange(0, self.iceDepth, dz)
            self.nprof_in = self.n_ice + (self.n_surf - self.n_ice) * np.exp(-1*self.k_ref*self.zprof_in)

        else:
            raise ValueError(
                f"Unknown refractive-index mode: "
                f"{self.ref_index_data_mode}. "
                "Expected 'data' or '1exp'."
            )

def nProfile_data(R, zprof_data, nprof_data, z_shift, iceDepth):
    z_meep = R[2]  # Depth coordinates in Meep
    z_true = z_meep - z_shift  # True depth
    if z_true <= iceDepth:
        ii_z = findNearest(zprof_data, z_true)
        n_z = nprof_data[ii_z]
    else:
        ii_z = findNearest(zprof_data, iceDepth)
        n_z = nprof_data[ii_z]
    return mp.Medium(index=n_z, D_conductivity=0)

def nProfile_1exp(R, n_ice, n_surf, k):
    z = R[2]
    if z > 0:
        return mp.Medium(index=nair)
    else:
        z_depth = -1 * z
        return mp.Medium(index=n_ice + (n_surf-n_ice)*math.exp(-k * z_depth), D_conductivity=0)

def pulse_meep_func(t, pulse_in, tspace_in):
    tspace_m = tspace_in * c_mGHz # Meep Time Domain - units of distance
    if t < max(tspace_m):
        ii = findNearest(tspace_m, t)
        return pulse_in[ii]
    else:
        return 0

def set_simulation_cylinder(sim_settings_in):
    iceDepth = sim_settings_in.iceDepth  # depth of ice
    airHeight = sim_settings_in.airHeight  # height of air
    iceRange = sim_settings_in.iceRange  # radius of domain
    boreholeRadius = sim_settings_in.boreholeRadius  # radius of borehole
    pad = sim_settings_in.pad
    sourceDepth = sim_settings_in.sourceDepth
    resolution = sim_settings_in.resolution

    R_tot = iceRange + sim_settings_in.rangeBuffer  # + pad + dpml# Total Geometry Radius (cylindrical coordinate system) including the padded region
    R_cent = boreholeRadius / 2 + R_tot / 2  # Center of the Geometry (here center means half of the radius)
    Z_tot = iceDepth + airHeight + 2 * pad  # Total Geometry Height: Including Ice and Air and the padded region
    Delta_Z = airHeight / 2 - iceDepth / 2

    sourceDepth_meep = sourceDepth + Delta_Z
    # Adjust Height to Meep coordinates - Meep enforces size symmetry about the x and z-axes

    H_aircent = airHeight / 2 + Delta_Z  # Central Height of Air #
    Z_icecent = iceDepth / 2 + Delta_Z  # Central Depth of Ice
    r_cent = boreholeRadius / 2  # Centre of Borehole
    iceRange_wo_bh = R_tot - boreholeRadius  # size of Ice Block without the borehole

    print("Profile points:", len(sim_settings_in.zprof_in))
    print("Depth range:", np.min(sim_settings_in.zprof_in), np.max(sim_settings_in.zprof_in))
    print("Index range:", np.min(sim_settings_in.nprof_in), np.max(sim_settings_in.nprof_in))

    # Ice Model
    if sim_settings_in.ref_index_data_mode == "data":
        def nProfile_in(R, zprof_data=sim_settings_in.zprof_in, nprof_data=sim_settings_in.nprof_in, z_shift=Delta_Z, iceDepth=iceDepth):
            z_meep = R[2]  # Depth coordinates in Meep
            z_true = z_meep - z_shift  # True depth
            if z_true <= iceDepth:
                ii_z = findNearest(zprof_data, z_true)
                n_z = nprof_data[ii_z]
            else:
                ii_z = findNearest(zprof_data, iceDepth)
                n_z = nprof_data[ii_z]
            return mp.Medium(index=n_z, D_conductivity=0)
    elif sim_settings_in.ref_index_data_mode == '1exp':
        def nProfile_in(R, n_ice=sim_settings_in.n_ice, n_surf=sim_settings_in.n_surf, k=sim_settings_in.k_surf):
            z = R[2]
            if z > 0:
                return mp.Medium(index=nair)
            else:
                z_depth = -1 * z
                return mp.Medium(index=n_ice + (n_surf - n_ice) * math.exp(-k * z_depth), D_conductivity=0)
    else:
        raise ValueError("Unknown index data mode, must be data or 1exp")
    ##**********************Simulation Setup*******************************##
    dimensions = mp.CYLINDRICAL
    if sim_settings_in.absorb_mode == 1:
        pml_layers = [mp.Absorber(thickness=pad)]
    else:
        pml_layers = [mp.PML(thickness=pad)]

    cell = mp.Vector3(2 * R_tot, mp.inf, Z_tot)
    geometry_dipole = [
        mp.Block(center=mp.Vector3(r_cent, 0, Z_icecent),
                 size=mp.Vector3(boreholeRadius, mp.inf, iceDepth),
                 material=mp.Medium(index=nair, D_conductivity=0)),
        mp.Block(center=mp.Vector3(R_cent, 0, H_aircent),
                 size=mp.Vector3(iceRange_wo_bh, mp.inf, airHeight),
                 material=mp.Medium(index=nair, D_conductivity=0)),
        mp.Block(center=mp.Vector3(R_cent, 0, Z_icecent),
                 size=mp.Vector3(iceRange_wo_bh, mp.inf, iceDepth),
                 material=nProfile_in)
    ]

    # Define Signal
    pulse_in_ns = sim_settings_in.pulse_in
    tspace_in_ns = sim_settings_in.tspace_in
    sources_dipole = []
    def pulse_meep(t, pulse_in=pulse_in_ns, tspace_in=tspace_in_ns):
        return pulse_meep_func(t, pulse_in, tspace_in)

    source1 = mp.Source(mp.CustomSource(src_func=pulse_meep),
                        component=mp.Ez,
                        center=mp.Vector3(sim_settings_in.sourceRange, 0, sourceDepth_meep))
    sources_dipole.append(source1)
    # create simulation
    sim_dipole = mp.Simulation(force_complex_fields=False,
                               cell_size=cell,
                               dimensions=mp.CYLINDRICAL,
                               boundary_layers=pml_layers,
                               geometry=geometry_dipole,
                               sources=sources_dipole,
                               resolution=resolution)
    # Define Receivers
    rxList = sim_settings_in.rxList
    rxList_meep = []
    nRx = len(rxList)
    for i in range(nRx):
        rx_x = rxList[i][0]
        rx_z = rxList[i][1]
        pt_meep_ij = mp.Vector3(rx_x, mp.inf, rx_z + Delta_Z)
        rxList_meep.append(pt_meep_ij)
    return sim_dipole, rxList_meep

def create_simulation_output(fname_out,settings,parallel_mode=False, comm=None):
    if parallel_mode:
        if comm is None:
            raise ValueError("An MPI communicator is required for parallel output")
        output_hdf = h5py.File(
            fname_out,
            "w",
            driver="mpio",
            comm=comm
        )
    else:
        output_hdf = h5py.File(fname_out, "w")

    with output_hdf as hdf:

        nRx = len(settings.rxList)

        # Create initially empty receiver datasets
        hdf.create_dataset(
            "rxPulses_r",
            shape=(nRx, 0),
            maxshape=(nRx, None),
            dtype="complex128",
            chunks=(1, settings.n_buffer)
        )

        hdf.create_dataset(
            "rxPulses_z",
            shape=(nRx, 0),
            maxshape=(nRx, None),
            dtype="complex128",
            chunks=(1, settings.n_buffer)
        )

        # Simulation metadata
        hdf.attrs["iceDepth"] = settings.iceDepth
        hdf.attrs["airHeight"] = settings.airHeight
        hdf.attrs["iceRange"] = settings.iceRange
        hdf.attrs["boreholeRadius"] = settings.boreholeRadius
        hdf.attrs["sourceDepth"] = settings.sourceDepth
        hdf.attrs["sourceRange"] = settings.sourceRange

        hdf.attrs["dt_ns_res"] = settings.dt_ns
        hdf.attrs["dt"] = settings.dt_ns_deci
        hdf.attrs["dt_meep"] = settings.dt_meep
        hdf.attrs["decimation_factor"] = settings.decimation_factor

        hdf.attrs["res"] = settings.resolution
        hdf.attrs["n_buffer"] = settings.n_buffer
        hdf.attrs["pad"] = settings.pad
        hdf.attrs["absorb_mode"] = settings.absorb_mode

        # Save the pre-defined data
        datasets = {
            "txPulse": settings.pulse_in,
            "tspace_tx": settings.tspace_in,
            "rxList": settings.rxList,
            "zProfile": settings.zprof_in,
            "nProfile": settings.nprof_in
        }
        for name, data in datasets.items():
            print(f"Rank {comm.rank}: creating {name}", flush=True)

            ds = hdf.create_dataset(name, shape=data.shape, dtype=data.dtype)

            print(f"Rank {comm.rank}: created {name}", flush=True)

            with ds.collective:
                ds[:] = data

            print(f"Rank {comm.rank}: finished writing {name}", flush=True)

def flush_receiver_buffers(
    pulse_r_ds,
    pulse_z_ds,
    pulse_r_buffer,
    pulse_z_buffer,
    n_samples
):
    if n_samples == 0:
        return

    nRx = pulse_r_buffer.shape[0]

    old_size = pulse_r_ds.shape[1]
    new_size = old_size + n_samples

    pulse_r_ds.resize((nRx, new_size))
    pulse_z_ds.resize((nRx, new_size))

    with pulse_r_ds.collective:
        pulse_r_ds[:, old_size:new_size] = pulse_r_buffer[:, :n_samples]

    with pulse_z_ds.collective:
        pulse_z_ds[:, old_size:new_size] = pulse_z_buffer[:, :n_samples]