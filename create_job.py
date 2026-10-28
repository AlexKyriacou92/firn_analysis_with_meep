import os
import subprocess
import sys
import configparser
from cluster import create_meep_job_from_config, submit_job

def main(fname_config, submit_bool = False, override_bool = False):
    fname_shell = create_meep_job_from_config(fname_config, override_bool)
    if submit_bool == True:
        print('Create sh script: ', fname_shell)
        print('Submitting job: ', fname_shell)
        submit_job(fname_shell)
        return -1
    else:
        print('Create sh script: ', fname_shell)
        return -1

if __name__ == "__main__":
    if len(sys.argv) == 4:
        config_file = sys.argv[1]
        submit_int = int(sys.argv[2])
        override_int = int(sys.argv[3])
    elif len(sys.argv) == 3:
        config_file = sys.argv[1]
        submit_int = int(sys.argv[2])
        override_int = 0
    elif len(sys.argv) == 2:
        config_file = sys.argv[1]
        submit_int = 0
        override_int = 0
        print('Assuming submit_bool = False, job must be submitted with sbatch manually')
    elif len(sys.argv) == 1:
        config_file = 'config-cluster.txt'
        submit_int = 0
        override_int = 0
        print('Assuming submit_bool = False, job must be submitted with sbatch manually')
    else:
        raise ValueError('Too many arguments, script is python ', sys.argv[0] + '<config_file?> <submit_int?>')
    if submit_int == 1:
        submit_bool = True
    elif submit_int == 0:
        submit_bool = False
    else:
        raise ValueError('submit_int must be 0 (False) or 1 (True)')
    if override_int == 1:
        override_bool = True
    elif override_int == 0:
        override_bool = False
    else:
        raise ValueError('override_int must be 0 (False) or 1 (True)')
    main(fname_config=config_file, submit_bool=submit_bool, override_bool=override_bool)
