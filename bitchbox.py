# sudo apt-get install pip libssl-dev
# sudo pip install scp

import hashlib
import os
import subprocess
from scp import SCPClient
from paramiko import AutoAddPolicy, SSHClient
import gradle

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
_replace_files = {"local.properties" : "sdk.dir={}".format(_remote_sdk_dir)}

_gradle_properties_path_local = "~/.gradle/gradle.properties"
_gradle_properties_path_temp = "/.gradle.properties"
_gradle_properties_path_remote = "/gradle.properties"
_gradle_properties_add = {"sdk.dir":_remote_sdk_dir}
_gradle_properties_remove = ["org.gradle.jvmargs"]

#####
def preparePath(path):
    return os.path.expanduser(path)

#####
def md5(str):
    return hashlib.md5(str).hexdigest()

#####
def md5File(fname):
    md5 = hashlib.md5()
    with open(fname, 'rb') as f:
        while True:
            data = f.read(4096)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()

#####
def createSSHClient(server, port, user):
    client = SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(AutoAddPolicy())
    client.connect(server, port, user)  # assumes public key access via default keyfile
    return client
    ### Usage Example
    # ssh = createSSHClient(_remote_server, _remote_port, _remote_user)
    # scp = SCPClient(ssh.get_transport())

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

####
def generateGradleProps():
    g = gradle.GradleProperties(preparePath(_gradle_properties_path_local))
    g.addDict(_gradle_properties_add)
    g.removeArray(_gradle_properties_remove)
    return g.generate()

print generateGradleProps()