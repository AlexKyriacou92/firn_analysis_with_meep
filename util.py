import numpy as np
import math
import h5py
import sys
from sys import argv, exit
import configparser
from scipy.signal import butter, lfilter

from math import pi
from numpy import rad2deg, deg2rad, sin, cos, sqrt, log, exp, log10
import scipy.signal as sig

nice = 1.78
c_mGHz = 0.3
nair = 1.0

def butterBandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def butterBandpassFilter(data, lowcut, highcut, fs, order=3):
    b, a = butterBandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y

def butterHighpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = sig.butter(order, normal_cutoff, btype='high', analog=False)
    return b, a

def butterHighpassFilter(data, cutoff, fs, order=5):
    b, a = butterHighpass(cutoff, fs, order=order)
    y = sig.filtfilt(b, a, data)
    return y

def butterLowpass(highcut, fs, order=5):
    nyq = 0.5 * fs
    high = highcut / nyq
    b, a = butter(order, high, btype='low')
    return b, a

def butterLowpassFilter(data, highcut, fs, order=3):
    b, a = butterLowpass(highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y

def findNearest(array, value):
    array = np.asarray(array, dtype='complex')
    idx = (np.abs(array - value)).argmin()
    return idx#array[idx]

def get_data(fname_txt):
    n_data = np.genfromtxt(fname_txt)
    zprof = n_data[:,0]
    nprof = n_data[:,1]
    return nprof, zprof

def get_index_from_rxList(rxList, x, z):
    nRx = len(rxList)
    dr_list = np.zeros(nRx)
    for i in range(nRx):
        x_rx_i = rxList[i, 0]
        z_rx_i = rxList[i, 1]
        dx = abs(x_rx_i - x)
        dz = abs(z_rx_i - z)
        dr_sq = dx ** 2 + dz ** 2
        dr = np.sqrt(dr_sq)
        dr_list[i] = dr
    ii_rx = np.argmin(dr_list)
    return ii_rx

def add_data_to_hdf(hdf_in, label, dataset):
    '''
    if label in hdf_in.keys():
        hdf_in[label] = dataset
    else:
        hdf_in.create_dataset(label, data=dataset)
    '''
    #Check if label exists
    check_bool = label in hdf_in.keys()
    if check_bool == False:
        hdf_in.create_dataset(label, data=dataset)