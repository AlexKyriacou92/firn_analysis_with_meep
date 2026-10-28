import numpy as np
import h5py
#import matplotlib.pyplot as pl

from simulation import sim_settings
from util import get_index_from_rxList

class simulation_reader:
    def __init__(self, fname_hdf):
        self.fname = fname_hdf
        self.settings = sim_settings(fname_config=None, fname_hdf=self.fname)
        self.data_from_hdf()

    def data_from_hdf(self):
        with h5py.File(self.fname, "r") as input_hdf:
            self.rxPulses_z = np.array(input_hdf["rxPulses_z"])
            self.rxPulses_r = np.array(input_hdf["rxPulses_r"])
        # Get the Spectra of the Pulses
        self.rxList = self.settings.rxList

        self.nRx = self.rxPulses_z.shape[0]
        self.nSamples = self.rxPulses_z.shape[1]
        self.dt = self.settings.dt_ns_deci # TODO: Check this is the right dt

        self.nFreq = self.nSamples // 2 + 1
        self.rxSpectra_z = np.zeros((self.nRx, self.nFreq), dtype=complex)
        self.rxSpectra_r = np.zeros((self.nRx, self.nFreq), dtype=complex)
        self.fspace = np.fft.rfftfreq(self.nSamples, self.dt)
        print(self.nRx, len(self.rxList))
        print(self.rxSpectra_z.shape, self.rxSpectra_r[0].dtype)
        for i in range(self.nRx):
            self.rxSpectra_z[i] = np.fft.rfft(self.rxPulses_z[i].real)
            self.rxSpectra_r[i] = np.fft.rfft(self.rxPulses_r[i].real)

        self.txPulse = self.settings.pulse_in
        self.tspace_tx = self.settings.tspace_in
        self.nSamples_tx = len(self.txPulse)
        self.fspace_tx = np.fft.rfftfreq(self.nSamples_tx, self.dt)
        self.txSpectra = np.fft.rfft(self.txPulse)


        self.nProfile = self.settings.nprof_in
        self.zProfile = self.settings.zprof_in
        self.sourceDepth = self.settings.sourceDepth
        self.sourceRange = self.settings.sourceRange
        self.airHeight = self.settings.airHeight

        self.iceRange = self.settings.iceRange
        self.iceDepth = self.settings.iceDepth
        self.tspace_rx = np.linspace(0, self.nSamples*self.dt, self.nSamples)

    def get_rx_actual(self, x_rx, z_rx):
        ii_rx = get_index_from_rxList(self.rxList, x_rx, z_rx)
        return self.rxList[ii_rx,0], self.rxList[ii_rx,1]

    def get_rx_pulse_z(self, x_rx, z_rx):
        ii_rx = get_index_from_rxList(self.rxList, x_rx, z_rx)
        rx_pulse_out = self.rxPulses_z[ii_rx]
        return rx_pulse_out

    def get_rx_pulse_r(self, x_rx, z_rx):
        ii_rx = get_index_from_rxList(self.rxList, x_rx, z_rx)
        rx_pulse_out = self.rxPulses_r[ii_rx]
        return rx_pulse_out

    def get_rx_spec_z(self, x_rx, z_rx):
        ii_rx = get_index_from_rxList(self.rxList, x_rx, z_rx)
        rx_spec_out = self.rxSpectra_z[ii_rx]
        return rx_spec_out

    def get_rx_spec_r(self, x_rx, z_rx):
        ii_rx = get_index_from_rxList(self.rxList, x_rx, z_rx)
        rx_spec_out = self.rxSpectra_r[ii_rx]
        return rx_spec_out