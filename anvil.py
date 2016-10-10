# sudo apt-get install pip libssl-dev
# sudo pip install scp

import hashlib
import json
import os
import subprocess
from StringIO import StringIO

from configparser import ConfigParser
from paramiko import AutoAddPolicy, SSHClient

#####
# CONFIG
#####
# TODO: Add ArgParse functionality for manual override of config file value
# Sunny@Macintosh || ~/Documents || rsync -rzP -e "ssh -p 9022" foot-locker worker@drone.local:~/rsync/

CONFIG_FILE = '~/Documents/Anvil/footlocker.anvil'

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
class JsonConfig(object):

    filename = ""
    unknown_fields = {}

    #####
    def __init__(self, filename = ""):
        if filename is not None and filename.__len__() != 0:
            self.filename = preparePath(filename)
            self.parse()

    #####
    def trimList(self, haystack = {}, needles = {}):
        result = dict(haystack)
        for key in needles.keys():
            if result.has_key(key):
                del result[key]
        return result

    #####
    def stripFunctions(self, fields = {}):
        result = dict(fields)
        for key, value in fields.iteritems():
            if (isinstance(value, type(preparePath)) or (key.startswith("__"))) and fields.has_key(key):
                del result[key]
        return result

    #####
    def parse(self):
        fields = self.getFields()
        if os.path.exists(self.filename):
            with open(self.filename) as f:
                cfg = json.load(f)
                for key, value in cfg.iteritems():
                    if fields.has_key(key):
                        self.__setattr__(key, value)
                    else:
                        self.unknown_fields[key] = value

    #####
    def getFields(self):
        subFields = self.__class__.__dict__
        fields = self.stripFunctions(subFields)
        return fields

#####
class AnvilConfig(JsonConfig):

    # Project file location
    project_parent_dir = None
    project_dir_name = None
    # Remote
    remote_user = None
    remote_server = None
    remote_port = None
    remote_public_key = None
    remote_destination_dir = None
    # rsync
    exclude_from_files = []
    exclude_files = []
    # gradle
    gradle_properties_path_local = None
    gradle_properties_path_remote_filename = None
    gradle_properties_add = {}
    gradle_properties_remove = []

    #####
    def __init__(self, filename):
        super(AnvilConfig, self).__init__(filename)

    # def test(self):

#####
class GradleProperties(object):

    KEY = "dummy"
    HEADER = "# auto-generated gradle.properties"
    config = ConfigParser

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

    thisconfig = AnvilConfig

    localPath = ""
    destPath = ""
    tempGradlePropsFilepath = ""

    def __init__(self, config = AnvilConfig):
        super(SourceSync, self).__init__()
        self.thisconfig = config
        self.localPath = preparePath("{}{}/".format(self.config.project_dir, self.config.project))
        self.destPath = "{}{}/".format(self.config.remote_destination_dir, self.config.project)
        self.tempGradlePropsFilepath = "{}/.gradle.properties".format(self.localPath)

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
        sshPort = 'ssh -p {}'.format(self.config.remote_port)
        cmd = ["rsync", "-zP", "-e", sshPort]
        return cmd

    #####
    def rsyncRemotePath(self, remoteFileDir):
        return '{}@{}:{}'.format(self.config.remote_user, self.config.remote_server, remoteFileDir)

    #####
    def syncSourceDir(self):
        #TODO Logic for custom public key
        dest = self.rsyncRemotePath(self.destPath)

        ## Build the rsync command
        rsync = self.rsyncCmd()
        rsync.append("-r")
        for file in self.config.exclude_files:
           rsync.append('--exclude=\"{}\"'.format(file))
        for file in self.config.exclude_from_files:
            rsync.append("--exclude-from={}".format(file))
        rsync.append("--exclude=\"{}\"".format(self.tempGradlePropsFilepath))
        rsync.append(self.localPath)
        rsync.append(dest)
        ## Execute. #TODO Interpret the outcome of rsync
        subprocess.call(rsync)

    #####
    def generateGradleProps(self):
        g = GradleProperties(preparePath(self.config.gradle_properties_path_local))
        g.addDict(self.config.gradle_properties_add)
        g.removeArray(self.config.gradle_properties_remove)
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
            destFilename = "{}{}".format(self.destPath, self.config.gradle_properties_path_remote_filename)
            dest = self.rsyncRemotePath(destFilename)
            rsync = self.rsyncCmd()
            rsync.append(self.tempGradlePropsFilepath)
            rsync.append(dest)
            ## Execute. #TODO interpret outcome of rsync
            subprocess.call(rsync)

#####
# RUNTIME
#####
config = AnvilConfig(CONFIG_FILE)
#sync = SourceSync(config)
# sync.syncSourceDir()
# sync.updateGradleProperties()
