# sudo apt-get install pip libssl-dev
# sudo pip install scp

import os #path.expandUser("~/filename")
import scp
import subprocess
import paramiko

# Sunny@Macintosh || ~/Documents || rsync -rzP -e "ssh -p 9022" foot-locker worker@drone.local:~/rsync/
_project_dir =  "~/Documents/"
_project =      "foot-locker"

_remote_user = "worker"
_remote_server = "drone.local"
_remote_port = "9022"
_remote_public_key = "~/.ssh/drone.pub"
_remote_destination = "~/rsync/"
_remote_sdk_dir = "/usr/lib/android-sdk"

_exclude_from = "/.gitignore"
_exclude_files = [".git/", "app/build/", ".gradle", ".idea", "*.apk"]
# IDEA: Parse .gitignore for exclude definitions
_replace_files = {"local.properties" : "sdk.dir={}".format(_remote_sdk_dir)}
_extra_files = {"~/.gradle/gradle.properties":"~/.gradle/gradle.properties"}


def createSSHClient(server, port, user, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client

def preparePath(path):
    return os.path.expanduser(path)

ssh = createSSHClient(_remote_server, _remote_port, _remote_user, password)
scp = SCPClient(ssh.get_transport())


#####
def rsyncSourceDir():
    #TODO Logic for custom public key
    #sshPort = 'ssh -p {} -i {}'.format(_remote_port, _remote_public_key)
    sshPort = 'ssh -p {}'.format(_remote_port)
    dest = '{}@{}:{}'.format(_remote_user, _remote_server, _remote_destination)
    excludeFromFile = preparePath(_project_dir + _project + _exclude_from)
    projectDir = preparePath(_project_dir + _project)

    ## Build the rsync command
    cmd = ["rsync", "-rzP"]
    for file in _exclude_files:
       cmd.append('--exclude=\"{}\"'.format(file))
    cmd.append("--exclude-from={}".format(excludeFromFile))
    cmd.append("-e")
    cmd.append(sshPort)
    cmd.append(projectDir)
    cmd.append(dest)
    ## Execute. #TODO Interpret the outcome of cmd
    subprocess.call(cmd)

##