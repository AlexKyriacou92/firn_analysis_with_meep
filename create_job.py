import os
import subprocess
import sys
import configparser
from cluster import create_meep_job_from_config, submit_job

def main(fname_config, submit_bool = False):
    fname_shell = create_meep_job_from_config(fname_config)
    if submit_bool == True:
        print('Create sh script: ', fname_shell)
        print('Submitting job: ', fname_shell)
        submit_job(fname_shell)
        return -1
    else:
        print('Create sh script: ', fname_shell)
        return -1

if __name__ == "__main__":
    if len(sys.argv) == 3:
        config_file = sys.argv[1]
        submit_int = int(sys.argv[2])
        if submit_int == 1:
            submit_bool = True
        elif submit_int == 0:
            submit_bool = False
        else:
            raise ValueError('submit_int must be 0 (False) or 1 (True)')
    elif len(sys.argv) == 2:
        config_file = sys.argv[1]
        submit_bool = False
        print('Assuming submit_bool = False, job must be submitted with sbatch manually')
    elif len(sys.argv) == 1:
        config_file = 'config-cluster.txt'
        submit_bool = False
        print('Assuming submit_bool = False, job must be submitted with sbatch manually')
    else:
        raise ValueError('Too many arguments, script is python ', sys.argv[0] + '<config_file?> <submit_int?>')
    main(fname_config=config_file, submit_bool=submit_bool)
