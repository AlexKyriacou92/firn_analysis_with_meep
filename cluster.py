import os
import subprocess
import sys
import configparser

class cluster_settings:
    def __init__(self, fname_config=None):
        if fname_config is not None:
            self.set_from_config(fname_config)
        else:
            raise ValueError('Supply fname_config to initialize config file')

    def set_from_config(self, fname_config):
        config = configparser.ConfigParser()
        config.read(fname_config)
        cluster_config = config['CLUSTER']

        self.nodes_min = int(cluster_config['NODES_MIN'])
        self.nodes_max = int(cluster_config['NODES_MAX'])
        if self.nodes_min < 1:
            raise ValueError('Nodes min must be greater than 1')
        if self.nodes_max < 1:
            raise ValueError('Nodes max must be greater than 1')
        if self.nodes_max < self.nodes_min:
            raise ValueError('nodes_max must be greater than or equal to nodes_min')

        self.partition = cluster_config['PARTITION']
        if 'ACCOUNT' in cluster_config.keys():
            self.account = cluster_config['ACCOUNT']
        else:
            self.account = None
        if 'MAIL' in cluster_config.keys():
            self.mail = cluster_config['MAIL']
        else:
            self.mail = None

        self.cpus_per_task = int(cluster_config['CPUS_PER_TASK'])
        if self.cpus_per_task < 1:
            raise ValueError('CPUS_PER_TASK must be greater than 0')
        self.tasks = int(cluster_config['TASKS'])
        if self.tasks < 1:
            raise ValueError('TASKS must be greater than 0')
        self.memory_per_cpu = int(cluster_config['MEMORY_PER_CPU']) # Define in MB
        if self.memory_per_cpu <= 0:
            raise ValueError('MEMORY_PER_CPU must be greater than 0 MB')
        self.days = int(cluster_config['DAYS'])
        if self.days < 0:
            raise ValueError('Days must be greater than 0')
        self.hours = int(cluster_config['HOURS'])
        if self.hours < 0:
            raise ValueError('hours must be greater than 0')


def create_meep_job_from_config(fname_config, override_bool):
    cluster_settings_in = cluster_settings(fname_config)
    config = configparser.ConfigParser()
    config.read(fname_config)
    job_settings = config['JOB']
    prefix = job_settings['prefix']
    mpi = job_settings['mpi']
    operator = job_settings['operator']
    script = job_settings['script']
    arg = job_settings['arg']
    command = mpi + ' -n ' + str(cluster_settings_in.tasks) + ' ' + operator + ' ' + script + ' ' + arg

    fname_shell = prefix + ".sh"
    if override_bool == False:
        i = 1
        while os.path.exists(fname_shell):
            fname_shell = f"{prefix}-{i}.sh"
            i += 1
    jobname = os.path.splitext(os.path.basename(fname_shell))[0]
    fname_out = jobname + ".out"

    sbatch = "#SBATCH"
    with open(fname_shell, 'w') as fout:
        #Write parameters of Sbatch
        fout.write("#!/bin/sh\n")

        minutes = 0
        seconds = 0
        fout.write(sbatch + " --job-name=" + jobname + "\n")
        fout.write(sbatch + " --partition=" + cluster_settings_in.partition + "\n")
        fout.write(sbatch + " --time=" + str(cluster_settings_in.days) + "-" + str(cluster_settings_in.hours) + ":" + str(minutes) + ":" + str(
            seconds) + "\n")
        if cluster_settings_in.nodes_min == cluster_settings_in.nodes_max:
            fout.write(sbatch + " --nodes=" + str(cluster_settings_in.nodes_min) + "\n")
        else:
            fout.write(sbatch + " --nodes=" + str(cluster_settings_in.nodes_min) + "-" + str(cluster_settings_in.nodes_max) + "\n")
        fout.write(sbatch + " --ntasks=" + str(cluster_settings_in.tasks) + "\n")
        fout.write(sbatch + " --cpus-per-task=" + str(cluster_settings_in.cpus_per_task) + "\n")
        if cluster_settings_in.account is not None:
            fout.write(sbatch + " --account=" + str(cluster_settings_in.account) + "\n")
        if cluster_settings_in.mail is not None:
            fout.write(sbatch + " --mail-user=" + str(cluster_settings_in.mail) + "\n")
        fout.write(sbatch + " --mem-per-cpu=" + str(cluster_settings_in.memory_per_cpu) + " # in MB\n")
        fout.write(sbatch + " -o " + str(fname_out) + "\n")
        fout.write(command)
    return fname_shell

def submit_job(fname_sh):
    result = subprocess.run(
        ["sbatch", fname_sh],
        check=True,
        capture_output=True,
        text=True
    )
    print(result.stdout.strip())