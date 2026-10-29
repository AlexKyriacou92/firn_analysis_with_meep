import numpy as np
import sys

if len(sys.argv) < 2:
    print("Usage: python create_rx_list.py <output_file>")
    sys.exit(1)
else:
    fname_rx_list = sys.argv[1]

rx_x_arr = np.arange(5, 200, 5)
rx_z_arr_1 = np.arange(1, 16, 2)
rx_z_arr_2 = np.arange(20, 90, 10)
rx_z_arr_3 = np.arange(90, 101, 1)
rx_z_arr = np.append(rx_z_arr_1, rx_z_arr_2)
rx_z_arr = np.append(rx_z_arr, rx_z_arr_3)

nRx_x = len(rx_x_arr)
nRx_z = len(rx_z_arr)
print(f"Number of RX={nRx_x * nRx_z}")
with open(fname_rx_list, 'w') as f:
    for i in range(nRx_x):
        for j in range(nRx_z):
            rx_x = rx_x_arr[i]
            rx_z = rx_z_arr[j]
            line = f"{rx_x}\t{rx_z}\n"
            f.write(line)
print(f'Create RX list file successfully{fname_rx_list}')