# sudo apt-get install pip libssl-dev
# sudo pip install scp

import hashlib
import os
import subprocess
from ConfigParser import ConfigParser
from StringIO import StringIO

from paramiko import AutoAddPolicy, SSHClient

#####
# CONFIG
#####
# TODO: Move these variables into – 1) ArgParse, for command line invokation – 2) use JSON config files for easy project builds
# Sunny@Macintosh || ~/Documents || rsync -rzP -e "ssh -p 9022" foot-locker worker@drone.local:~/rsync/
_project_dir =  "~/Documents/"
_project =      "foot-locker"

_remote_user = "worker"
_remote_server = "drone.local"
_remote_port = "9022"
_remote_public_key = "~/.ssh/drone.pub"
_remote_destination_dir = "~/rsync/"
_remote_sdk_dir = "/usr/lib/android-sdk"

_exclude_from_files = ["/.gitignore"]
_exclude_files = [".git/", "app/build/", ".gradle", ".idea", "*.apk"]

_gradle_properties_path_local = "~/.gradle/gradle.properties"
_gradle_properties_path_remote_filename = "gradle.properties"
_gradle_properties_add = {"sdk.dir":_remote_sdk_dir}
_gradle_properties_remove = ["org.gradle.jvmargs"]

#####
# GLOBAL FUNCTIONS
#####
def preparePath(path):
    return os.path.expanduser(path)

#####
def createSSHClient(self, server, port, user):
    client = SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(AutoAddPolicy())
    client.connect(server, port, user)  # assumes public key access via default keyfile
    return client
    ### Usage Example
    # ssh = createSSHClient(_remote_server, _remote_port, _remote_user)
    # scp = SCPClient(ssh.get_transport())

#####
# CLASSES
#####
class GradleProperties(object):

    KEY = "dummy"
    HEADER = "# auto-generated gradle.properties"
    config = None

    #####
    def __init__(self, filename):
        self.config = ConfigParser(strict=False,interpolation=None)
        with open(filename) as f:
            vfilestr = '[{}]\n{}'.format(self.KEY, f.read())
            vfile = StringIO(vfilestr)
            self.config.read_file(vfile)

    #####
    def addDict(self, dict):
        for key, val in dict.iteritems():
            self.add(key, val)

    #####
    def add(self, key, val):
        self.config.set(self.KEY, key, val)

    #####
    def removeArray(self, array):
        for key in array:
            self.remove(key)

    #####
    def remove(self, key):
        self.config.remove_option(self.KEY, key)

    #####
    def generate(self):
        out = self.HEADER
        for key, val in self.config[self.KEY].iteritems():
            out = "{}\n{}={}".format(out, key, val)
        return out

    # addProps = {"sdk.dir":"/usr/lib/android-sdk", "test_val":"neatoSK33t0"}
    # gradle = GradleProperties("~/.gradle/gradle.properties")
    # gradle.addDict(addProps)
    # print gradle.generate()

#####
class SourceSync(object):

    localPath = preparePath("{}{}/".format(_project_dir, _project))
    destPath = "{}{}/".format(_remote_destination_dir, _project)
    tempGradlePropsFilepath = "{}/.gradle.properties".format(localPath)

    def __init__(self):
        super(SourceSync, self).__init__()

    #####
    def md5(self, str):
        return hashlib.md5(str).hexdigest()

    #####
    def md5File(self, fname):
        md5 = hashlib.md5()
        with open(fname, 'rb') as f:
            while True:
                data = f.read(4096)
                if not data:
                    break
                md5.update(data)
        return md5.hexdigest()

    #####
    def rsyncCmd(self):
        sshPort = 'ssh -p {}'.format(_remote_port)
        cmd = ["rsync", "-zP", "-e", sshPort]
        return cmd

    #####
    def rsyncRemotePath(self, remoteFileDir):
        return '{}@{}:{}'.format(_remote_user, _remote_server, remoteFileDir)

    #####
    def syncSourceDir(self):
        #TODO Logic for custom public key
        dest = self.rsyncRemotePath(self.destPath)

        ## Build the rsync command
        rsync = self.rsyncCmd()
        rsync.append("-r")
        for file in _exclude_files:
           rsync.append('--exclude=\"{}\"'.format(file))
        for file in _exclude_from_files:
            rsync.append("--exclude-from={}".format(file))
        rsync.append("--exclude=\"{}\"".format(self.tempGradlePropsFilepath))
        rsync.append(self.localPath)
        rsync.append(dest)
        ## Execute. #TODO Interpret the outcome of rsync
        subprocess.call(rsync)

    #####
    def generateGradleProps(self):
        g = GradleProperties(preparePath(_gradle_properties_path_local))
        g.addDict(_gradle_properties_add)
        g.removeArray(_gradle_properties_remove)
        return g.generate()

    #####
    def updateGradleProperties(self):
        newProps = self.generateGradleProps()
        if os.path.exists(self.tempGradlePropsFilepath):
            newMd5 = self.md5(newProps)
            oldMd5 = self.md5File(self.tempGradlePropsFilepath)
            if newMd5 == oldMd5:
                return
        with open(self.tempGradlePropsFilepath, 'w') as f:
            f.write(newProps)
            destFilename = "{}{}".format(self.destPath, _gradle_properties_path_remote_filename)
            dest = self.rsyncRemotePath(destFilename)
            rsync = self.rsyncCmd()
            rsync.append(self.tempGradlePropsFilepath)
            rsync.append(dest)
            ## Execute. #TODO interpret outcome of rsync
            subprocess.call(rsync)

#####
# RUNTIME
#####
sync = SourceSync()
sync.syncSourceDir()
sync.updateGradleProperties()