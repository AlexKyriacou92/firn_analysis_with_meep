import numpy
import h5py
#import matplotlib.pyplot as pl

from simulation import sim_settings
from util import get_index_from_rxList

class simulation_reader:
    def __init__(self, fname_hdf):
        self.fname = fname_hdf
        self.settings = sim_settings(self.fname)
        self.data_from_hdf()

    def data_from_hdf(self):
        with h5py.File(self.fname, "r") as input_hdf:
            self.rxPulses_z = np.array(input_hdf["rxPulses_z"])
            self.rxPulses_r = np.array(input_hdf["rxPulses_r"])
        self.rxList = self.settings.rxList
        self.txPulse = self.settings.pulse_in
        self.tspace_tx = self.settings.tspace_tx
        self.nProfile = self.settings.nprof_in
        self.zProfile = self.settings.zprof_in
        self.sourceDepth = self.settings.sourceDepth
        self.iceRange = self.settings.iceRange
        self.iceDepth = self.settings.iceDepth
        self.dt = self.settings.dt_ns_deci # TODO: Check this is the right dt
        self.nSamples = self.rxPulses_z.shape[1]
        self.tspace_rx = np.linsspace(0, self.nSamples*self.dt, self.nSamples)
        
    def get_rx_pulse_z(self, x_rx, z_rx):
        ii_rx = get_index_from_rxList(self.rxList, x_rx, z_rx)
        rx_pulse_out = self.rxPulses_z[ii_rx]
        return rx_pulse_out

    def get_rx_pulse_r(self, x_rx, z_rx):
        ii_rx = get_index_from_rxList(self.rxList, x_rx, z_rx)
        rx_pulse_out = self.rxPulses_r[ii_rx]
        return rx_pulse_out