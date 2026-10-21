import datetime
import numpy as np
import math
import h5py
import sys
import configparser
import meep as mp
import os
import time
import util
from util import butterBandpassFilter, get_data, findNearest

if len(sys.argv) == 2:
    fname_config = sys.argv[1]
else:
    fname_config = 'config-example.txt'

print('Initiating Simulation of a pulse generated from a point source inside a modelled ice-sheet (range-independent)')

config_file = os.path.join(os.path.dirname(__file__), fname_config)
config = configparser.ConfigParser()
config.read(config_file)
now = datetime.datetime.now()
print('Simulation Started at: ', now)
print('')

#Input Parameters
print('Input Parameters from config file', fname_config)

geometry = config['GEOMETRY']
print('Geometry:')
for key in geometry.keys():
    print(key, geometry[key])
source = config['SOURCE']
print('source:')
for key in source.keys():
    print(key, source[key])
settings = config['SETTINGS']
print('settings:')
for key in settings.keys():
    print(key, settings[key])
receiver = config['RECEIVER']
print('receiver:')
for key in receiver.keys():
    print(key, receiver[key])
ref_index = config['REFRACTIVE INDEX']
print('ref index')
for key in ref_index.keys():
    print(key, ref_index[key])


fname_prefix = settings['prefix']
fname_data = ref_index['data_file']

data_defined = receiver['data_defined']
if data_defined == True:
    fname_rx_list = receiver['rx_list']
    rx_list = get_data(fname_rx_list)
else:
    rx_x_min = float(receiver['rx_x_min'])
    rx_x_max = float(receiver['rx_x_max'])
    rx_dx = float(receiver['rx_dx'])
    rx_z_min = float(receiver['rx_z_min'])
    rx_z_max = float(receiver['rx_z_max'])
    rx_dz = float(receiver['rx_dz'])

    rx_x_l = np.arange(rx_x_min, rx_x_max + rx_dx, rx_dx)
    rx_z_l = np.arange(rx_z_min, rx_z_max + rx_dz, rx_dz)
    rx_list = []
    for i in range(len(rx_x_l)):
        for j in range(len(rx_z_l)):
            rx_list.append([rx_x_l[i], rx_z_l[j]])
    rx_list = np.array(rx_list)

nair = 1.0      # index of air
iceDepth = float(geometry['iceDepth'])  # depth of ice
airHeight = float(geometry['airHeight'])     # height of air
iceRange = float(geometry['iceRange']) #radius of domain
boreholeRadius = float(geometry['boreholeRadius']) #radius of borehole
pad = float(geometry['pad'])
dpml = pad # Changed from /2

sourceDepth = float(source['sourceDepth']) #depth of diple below ice
sourceRange = float(source['sourceRange']) + boreholeRadius/2

print('sourceDepth', sourceDepth)

a_scale = 1 # a = 1m

c_mMHz = 300.0 # m/us or m MHz
c_mGHz = 0.3 # m/ns or m GHz
c_meep = 1.0 #Speed of Light is set to 1 -> Scale Invariance of Maxwell's Equations

#RESOLUTION
nice = 1.78
resolution = float(geometry['resolution'])	#how many pixels per meter
mpp = 1/resolution    # meters per pixel, also dx
column_size = iceRange/mpp	# number of pixels in the column
vice = 1/nice   	# phase velocity in ice

# Set Decimation Factor
if 'decimation_factor' in receiver:
    decimation_factor = float(receiver['decimation_factor'])
else:
    decimation_factor = 1

#Set size of buffer for Ez and Er receiver data
if 'n_buffer' in receiver:
    n_buffer = int(receiver['n_buffer'])
else:
    n_buffer = 1000

t_start_ns = float(source['startTime']) #ns TODO: Make Start Time Controllable
t_start_meep = t_start_ns*c_mGHz
print('Start Time in [m]', t_start_meep)

S_courant = float(settings['S_courant']) #Courant Factor S -> dt = S dx / c or S mpp /c
dt_meep = S_courant * mpp

dt_ns = dt_meep/c_mGHz # Time resolution in FDTD
dt_us = dt_meep/c_mMHz #

dt_ns_deci = dt_ns * decimation_factor
print('dt_m = ', dt_meep, 'm (before decimation)')
print('dt_ns = ', dt_ns, 'ns (before decimation)')
print('dt_ns = ', dt_ns_deci, ' ns (after decimation)')
f_nyq_deci = 1/(2*dt_ns_deci)
print('f_nyq = ', f_nyq_deci, ' GHz (after decimation)')

iceMaxPath = iceRange #np.sqrt(iceRange**2 + iceDepth**2)
if 'cutoff_factor' in receiver:
    cutoff_factor = float(receiver['cutoff_factor'])
else:
    cutoff_factor = 1.1
t_end_meep = cutoff_factor*nice*iceMaxPath

t_end_ns = t_end_meep/c_mGHz

t_space_meep = np.arange(0, t_end_meep, dt_meep)
t_space_ns = t_space_meep * c_mGHz
nSteps = int(t_end_meep / dt_meep)
print('nSteps=',nSteps)

fsamp_MHz = 1/dt_us
wavel_samp = c_mMHz/fsamp_MHz # THIS IS THE SAME AS DT_M
fsamp_meep = 1/wavel_samp # 1 / DT_M
print('sample frequency', fsamp_MHz, 'MHz')

print('Size of Time Space =', len(t_space_meep), 'nSteps t_end_meep/mpp =', nSteps)
#Redefine Geometry for Meep
if 'rangeBuffer' in geometry:
    rangeBuffer = float(geometry['rangeBuffer'])
else:
    rangeBuffer = pad

R_tot = iceRange + rangeBuffer #+ pad + dpml# Total Geometry Radius (cylindrical coordinate system) including the padded region

R_cent = boreholeRadius/2 + R_tot/2 # Center of the Geometry (here center means half of the radius)

Z_tot = iceDepth + airHeight + 2*pad #Total Geometry Height: Including Ice and Air and the padded region
Delta_Z = airHeight/2 - iceDepth/2

sourceDepth_meep = sourceDepth + Delta_Z

#Adjust Height to Meep coordinates - Meep enforces size symmetry about the x and z-axes

H_aircent = airHeight/2 + Delta_Z # Central Height of Air #
Z_icecent = iceDepth/2 + Delta_Z # Central Depth of Ice
r_cent = boreholeRadius/2 # Centre of Borehole
iceRange_wo_bh = R_tot-boreholeRadius #size of Ice Block without the borehole

# Define Ice Model:
if ref_index['mode'] == 'data':
    nprof_data_in, zprof_data_in = get_data(ref_index['data_file'])

    def nProfile_in(R, zprof_data=zprof_data_in, nprof_data=nprof_data_in, z_shift=Delta_Z):
        z_meep = R[2] # Depth coordinates in Meep
        z_true = z_meep - z_shift # True depth
        if z_true <= iceDepth:
            ii_z = findNearest(zprof_data, z_true)
            n_z = nprof_data[ii_z]
        else:
            ii_z = findNearest(zprof_data, iceDepth)
            n_z = nprof_data[ii_z]
        return mp.Medium(index=n_z, D_conductivity=0)
else:
    # At the moment this is hard coded to be a simple exponential profile
    # TODO change this later
    def nProfile_in(R):
        z = R[2]
        if z > 0:
            return mp.Medium(index=n_air)
        else:
            z_depth = -1 * z
            A = 1.78
            B = 0.43
            C = 0.0132  # 1/m
            return mp.Medium(index=A - B * math.exp(-C * z_depth))


##*********************************************************************##

##**********************Simulation Setup*******************************##
dimensions = mp.CYLINDRICAL
if 'absorb_mode' in geometry:
    absorb_mode = int(geometry['absorb_mode'])
    if absorb_mode == 1:
        pml_layers = [mp.Absorber(thickness=pad)]
    else:
        pml_layers = [mp.PML(thickness=pad)]
else:
    absorb_mode = 0
    pml_layers = [mp.PML(thickness=pad)]

cell = mp.Vector3(2*R_tot, mp.inf, Z_tot)

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

#Define Signal
sources_dipole = []
if source['mode'] == 'impulse':
    t_center = float(source['startTime'])
    freq_LP = float(source['freq_LP'])
    freq_HP = float(source['freq_HP'])
    order = int(source['order'])
    wvf_impulse = np.zeros(nSteps)
    ii_center = int(t_center/dt_ns)
    wvf_impulse[ii_center] = 1.0
    pulse_in_0 = butterBandpassFilter(wvf_impulse, freq_HP, freq_LP, order)
    tspace_in_ns = t_space_ns
elif source['mode'] == 'data':
    fname_source = source['sourceFile']
    pulse_in_0, tspace_in_ns = get_data(fname_source)
else:
    print('error, unknown setting SOURCE:mode, must be: data or impulse')
    sys.exit()

print('nSteps=', nSteps)
print('len(pulse_in) = ', len(pulse_in_0), 'len(tspace_in)', len(tspace_in_ns))
tspace_meep = tspace_in_ns * c_mGHz
print('len(tspace_meep)', len(tspace_meep))
def pulse_meep(t, pulse_in=pulse_in_0, t_space_in=tspace_in_ns):
    tspace_meep = t_space_in * c_mGHz # Meep Time Domain - units of distance
    if t < max(tspace_meep):
        ii = findNearest(tspace_meep, t)
        return pulse_in[ii]
    else:
        return 0

source1 = mp.Source(mp.CustomSource(src_func = pulse_meep),
                    component=mp.Ez,
                    center=mp.Vector3(sourceRange, 0, sourceDepth_meep))
sources_dipole.append(source1)

# create simulation
sim_dipole = mp.Simulation(force_complex_fields=False,
                cell_size=cell,
                dimensions=mp.CYLINDRICAL,
                boundary_layers=pml_layers,
                geometry=geometry_dipole,
                sources=sources_dipole,
                resolution=resolution)

#=================================================================
# Get RX Functions
#================================================================
rxList_meep = []
rxList = []
nRx = len(rx_list)
for i in range(nRx):
    rx_x = rx_list[i][0]
    rx_z = rx_list[i][1]
    rxList.append([rx_x, rx_z])
    pt_meep_ij = mp.Vector3(rx_x, mp.inf, rx_z + Delta_Z)
    rxList_meep.append(pt_meep_ij)
print(rxList_meep)
rxList = np.array(rxList)

dt_C = S_courant*mpp

path2sim = settings['path2output']
if os.path.isdir(path2sim) == False:
    os.mkdir(path2sim)

fname_out = path2sim + '/' + fname_prefix + '_z_tx_' + str(sourceDepth) + '_buffer.h5'
if os.path.isfile(fname_out) == True:
    os.system('rm -f ' + fname_out)

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

# Open HDF5 File to Run Simulation
#with h5py.File(fname_out, 'a', driver='mpio', comm=MPI.COMM_WORLD) as output_hdf:
with h5py.File(fname_out, 'a') as output_hdf:
    pulse_r_label = 'rxPulses_r'
    pulse_z_label = 'rxPulses_z'

    pulse_r_ds = output_hdf.create_dataset(pulse_r_label, (nRx, 0), maxshape=(nRx, None), dtype='complex128')
    pulse_z_ds = output_hdf.create_dataset(pulse_z_label, (nRx, 0), maxshape=(nRx, None), dtype='complex128')

    output_hdf.attrs['iceDepth'] = iceDepth
    output_hdf.attrs['airHeight'] = airHeight
    output_hdf.attrs['iceRange'] = iceRange
    output_hdf.attrs['boreholeRadius'] = boreholeRadius
    output_hdf.attrs['sourceDepth'] = sourceDepth
    output_hdf.attrs['freq_samp'] = fsamp_MHz/1e3
    output_hdf.attrs['dt_ns_res'] = dt_ns
    output_hdf.attrs['dt'] = dt_ns_deci
    output_hdf.attrs['dt_meep'] = dt_meep
    output_hdf.attrs['decimation_factor'] = decimation_factor
    output_hdf.attrs['sourceRange'] = sourceRange
    output_hdf.attrs['res'] = resolution
    output_hdf.attrs['n_buffer'] = n_buffer
    output_hdf.attrs['pad'] = pad
    output_hdf.attrs['dpml'] = dpml
    output_hdf.attrs['absorb_mode'] = absorb_mode

    rx_label = 'rxList'
    zProfile_label = 'zProfile'
    nProfile_label = 'nProfile'
    txPulse_label = 'txPulse'

    add_data_to_hdf(output_hdf, txPulse_label, pulse_in_0)
    add_data_to_hdf(output_hdf, zProfile_label, zprof_data_in)
    add_data_to_hdf(output_hdf, nProfile_label, nprof_data_in)
    add_data_to_hdf(output_hdf, rx_label, rxList)
    add_data_to_hdf(output_hdf, 'tspace_tx', tspace_in_ns)

    factor = (dt_meep / dt_C) * decimation_factor
    # Buffers in memory
    pulse_r_buffer = np.zeros((nRx, n_buffer), dtype='complex128')
    pulse_z_buffer = np.zeros((nRx, n_buffer), dtype='complex128')

    # Buffer state tracker
    current_buffer_index = 0
    step_index = 0  # total number of samples stored so far


    def get_amp_at_t2(sim):
        global pulse_r_buffer, pulse_z_buffer, current_buffer_index, step_index

        # Store Ez and Ex fields into the buffer
        for i, rx_pt in enumerate(rxList_meep):
            pulse_r_buffer[i, current_buffer_index] = sim.get_field_point(mp.Ex, rx_pt)
            pulse_z_buffer[i, current_buffer_index] = sim.get_field_point(mp.Ez, rx_pt)

        current_buffer_index += 1
        step_index += 1

        # If the buffer is full, write it to disk
        if current_buffer_index == n_buffer:
            #print('Writing full buffer at step', step_index, '...')
            old_size = pulse_r_ds.shape[1]
            new_size = old_size + current_buffer_index  # pulse_r_ds.shape[1]

            pulse_r_ds.resize((nRx, new_size))
            pulse_z_ds.resize((nRx, new_size))
            for i in range(nRx):
                pulse_z_ds[i, old_size:new_size] = pulse_z_buffer[i, :current_buffer_index]
                pulse_r_ds[i, old_size:new_size] = pulse_r_buffer[i, :current_buffer_index]
            current_buffer_index = 0

    #Initialize Simulation
    print('Initialize Simulation')
    tstart_initial = time.time()
    sim_dipole.init_sim()
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
    sim_dipole.run(mp.at_every(dt_C * decimation_factor, get_amp_at_t2), until=t_end_meep)

    # ========== Final flush for leftover buffer ==========
    if current_buffer_index > 0:
        print('Final flush: writing remaining ', current_buffer_index, 'steps...')
        old_size = pulse_r_ds.shape[1]
        new_size = old_size + current_buffer_index #pulse_r_ds.shape[1]

        pulse_r_ds.resize((nRx, new_size))
        pulse_z_ds.resize((nRx, new_size))
        for i in range(nRx):
            pulse_z_ds[i, old_size:new_size] = pulse_z_buffer[i, :current_buffer_index]
            pulse_r_ds[i, old_size:new_size] = pulse_r_buffer[i, :current_buffer_index]

    print('')
    tend_run = time.time()
    now = datetime.datetime.now()
    duration = tend_run - tstart_run
    print('Simulation Run Complete at', now)
    print('Duration: ', datetime.timedelta(seconds=duration))

    now = datetime.datetime.now()
    print('Simulation Complete at', now)
    print('Data saved to ', fname_out)