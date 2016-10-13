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
# TODO: Make local anvil/ directory to hold the gradle.properties and retrieved builds

#####
# GLOBAL FUNCTIONS
#####
def preparePath(path):
    return os.path.expanduser(path)

#####
def createSSHClient(server, port, user):
    client = SSHClient()
    # client.load_system_host_keys()
    client.set_missing_host_key_policy(AutoAddPolicy())
    client.connect(server, username=user, port=int(port))  # assumes public key access via default keyfile
    return client
    ### Usage Example
    # ssh = createSSHClient(_remote_server, _remote_port, _remote_user)
    # scp = SCPClient(ssh.get_transport())

#####
# CLASSES
#####
# noinspection PyDefaultArgument
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
                        if type(value) == type(u'a'):
                            self.__setattr__(key, str(value))
                        else:
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
class ConfigWrapper(object):
    """
    Just a dumb way to pass around the same references.
    """

    config = AnvilConfig

    localPath = ""
    destPath = ""
    tempGradlePropsFilepath = ""

    def __init__(self, config = AnvilConfig):
        super(ConfigWrapper, self).__init__()
        self.config = config
        self.localPath = preparePath("{}{}/".format(self.config.project_parent_dir, self.config.project_dir_name))
        self.destPath = "{}{}/".format(self.config.remote_destination_dir, self.config.project_dir_name)
        self.tempGradlePropsFilepath = "{}/.gradle.properties".format(self.localPath)

#####
class AnvilOperator(object):

    cfg = ConfigWrapper

    def __init__(self, config = ConfigWrapper):
        super(AnvilOperator, self).__init__()
        self.cfg = config

#####
class SourceSync(AnvilOperator):
    """
    Handles the syncing of changes to local source code up to the build server.
    Also creates the custom gradle.properties file that is synced.
    """

    def __init__(self, config=ConfigWrapper):
        super(SourceSync, self).__init__(config)

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
        sshPort = 'ssh -p {}'.format(self.cfg.config.remote_port)
        cmd = ["rsync", "-zP", "-e", sshPort]
        return cmd

    #####
    def rsyncRemotePath(self, remoteFileDir):
        return '{}@{}:{}'.format(self.cfg.config.remote_user, self.cfg.config.remote_server, remoteFileDir)

    #####
    def syncSourceDir(self):
        #TODO Logic for custom public key
        dest = self.rsyncRemotePath(self.cfg.destPath)

        ## Build the rsync command
        rsync = self.rsyncCmd()
        rsync.append("-r")
        for file in self.cfg.config.exclude_files:
           rsync.append('--exclude=\"{}\"'.format(file))
        for file in self.cfg.config.exclude_from_files:
            rsync.append("--exclude-from={}{}".format(self.cfg.localPath, file))
        rsync.append("--exclude=\"{}\"".format(self.cfg.tempGradlePropsFilepath))
        rsync.append(self.cfg.localPath)
        rsync.append(dest)
        print rsync.c
        quit()
        ## Execute. #TODO Interpret the outcome of rsync
        subprocess.call(rsync)

    #####
    def generateGradleProps(self):
        g = GradleProperties(preparePath(self.cfg.config.gradle_properties_path_local))
        g.addDict(self.cfg.config.gradle_properties_add)
        g.removeArray(self.cfg.config.gradle_properties_remove)
        return g.generate()

    #####
    def updateGradleProperties(self):
        newProps = self.generateGradleProps()
        if os.path.exists(self.cfg.tempGradlePropsFilepath):
            newMd5 = self.md5(newProps)
            oldMd5 = self.md5File(self.cfg.tempGradlePropsFilepath)
            if newMd5 == oldMd5:
                return
        with open(self.cfg.tempGradlePropsFilepath, 'w') as f:
            f.write(newProps)
            destFilename = "{}{}".format(self.cfg.destPath, self.cfg.config.gradle_properties_path_remote_filename)
            dest = self.rsyncRemotePath(destFilename)
            rsync = self.rsyncCmd()
            rsync.append(self.cfg.tempGradlePropsFilepath)
            rsync.append(dest)
            ## Execute. #TODO interpret outcome of rsync
            subprocess.call(rsync)



class SourceBuilder(AnvilOperator):
    """
    Handles execution of the source build command and retreival of the console output.
    """

    client = SSHClient

    #####
    def __init__(self, config=ConfigWrapper):
        super(SourceBuilder, self).__init__(config)

    #####
    def initSshClient(self):
        self.client = createSSHClient(self.cfg.config.remote_server, self.cfg.config.remote_port, self.cfg.config.remote_user)

    #####
    def executeRemoteCommand(self, cmd=[]):
        self.initSshClient()
        cmd = "{}/gradlew -p {} assembleStagingDebug".format(self.cfg.destPath, self.cfg.destPath)
        stdin, stdout, stderr = self.client.exec_command('./gradle')
        for line in stdout:
            print '... ' + line.strip('\n')
        self.client.close()

#####
# RUNTIME
#####
config = AnvilConfig(CONFIG_FILE)
configWrapper = ConfigWrapper(config)

sync = SourceSync(configWrapper)
sync.syncSourceDir()
sync.updateGradleProperties()

build = SourceBuilder(configWrapper)
build.executeRemoteCommand(None)