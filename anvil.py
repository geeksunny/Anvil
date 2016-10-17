# sudo apt-get install pip libssl-dev
# sudo pip install scp configparser

import hashlib
import json
import os
import subprocess
from StringIO import StringIO

from configparser import ConfigParser
from paramiko import AutoAddPolicy, SSHClient
from scp import SCPClient

# TODO: Config files live in ~/.anvil/ - A global config file can apply to everything and individual config files
# TODO:     can replace [AND/OR supplement?] the global config. Command line arguments will take presedence over both.
#####
# CONFIG
#####
# TODO: Add ArgParse functionality for manual override of config file value
# Sunny@Macintosh || ~/Documents || rsync -rzP -e "ssh -p 9022" foot-locker worker@drone.local:~/rsync/

CONFIG_FILE = '~/Documents/Anvil/footlocker.anvil'
ANVIL_DIR_NAME = "anvil"


#####
# GLOBAL FUNCTIONS
#####
def prepare_path(path):
    return os.path.expanduser(path)


#####
def create_ssh_client(server, port, user):
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

    TYPE_MAPPING = {unicode: str}

    filename = ""
    unknown_fields = {}

    #####
    @staticmethod
    def trimlist(haystack={}, needles={}):
        result = dict(haystack)
        for key in needles.keys():
            if key in result:
                del result[key]
        return result

    #####
    @staticmethod
    def stripfunctions(fields={}):
        result = dict(fields)
        for key, value in fields.iteritems():
            if (isinstance(value, type(prepare_path)) or (key.startswith("__"))) and key in fields:
                del result[key]
        return result

    #####
    def __init__(self, filename=""):
        if filename is not None and filename.__len__() != 0:
            self.filename = prepare_path(filename)
            self.parse()

    #####
    def getvalue(self, value):
        _typefrom = type(value)
        if _typefrom in self.TYPE_MAPPING:
            _typeto = self.TYPE_MAPPING[_typefrom]
            return _typeto(value)
        else:
            return value

    #####
    def parse(self):
        fields = self.getfields()
        if os.path.exists(self.filename):
            with open(self.filename) as f:
                cfg = json.load(f)
            for key, value in cfg.iteritems():
                if key in fields:
                    self.__setattr__(key, self.getvalue(value))
                else:
                    self.unknown_fields[key] = self.getvalue(value)

    #####
    def getfields(self):
        sub_fields = self.__class__.__dict__
        fields = self.stripfunctions(sub_fields)
        return fields


#####
class AnvilConfig(JsonConfig):

    # Project file location
    project_parent_dir = ""
    project_dir_name = ""
    # Remote
    remote_user = ""
    remote_server = ""
    remote_port = int
    remote_public_key = ""
    remote_destination_dir = ""
    remote_result_dir = ""
    remote_result_file = ""
    # rsync
    exclude_from_files = []
    exclude_files = []
    # gradle
    gradle_properties_path_local = ""
    gradle_properties_path_remote = ""
    gradle_properties_add = {}
    gradle_properties_remove = []
    gradle_local_properties_filename = ""
    gradle_local_properties_contents = {}
    gradle_build_wrapper_file = ""
    gradle_build_wrapper_task = ""

    #####
    def __init__(self, filename):
        super(AnvilConfig, self).__init__(filename)

#####
class GradleProperties(object):

    KEY = "dummy"
    HEADER = "# auto-generated gradle properties\n"
    config = ConfigParser

    #####
    def __init__(self, filename):
        self.config = ConfigParser(strict=False,interpolation=None)
        self.config.optionxform = str
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
            out = "{}{}={}\n".format(out, key, val)
        return out

    # addProps = {"sdk.dir":"/usr/lib/android-sdk", "test_val":"neatoSK33t0"}
    # gradle = GradleProperties("~/.gradle/gradle.properties")
    # gradle.addDict(addProps)
    # print gradle.generate()

#####
class ConfigWrapper(object):
    """Just a dumb way to pass around the same references."""

    config = AnvilConfig
    ssh_client = SSHClient

    local_path = ""
    dest_path = ""

    #####
    def __init__(self, config = AnvilConfig):
        super(ConfigWrapper, self).__init__()
        self.config = config
        self.local_path = prepare_path("{}{}/".format(self.config.project_parent_dir, self.config.project_dir_name))
        self.dest_path = "{}{}/".format(self.config.remote_destination_dir, self.config.project_dir_name)
        self.setupLocalDir()

    #####
    def setupLocalDir(self):
        localDir = "{}{}/".format(self.local_path, ANVIL_DIR_NAME)
        if not os.path.exists(localDir):
            os.makedirs(localDir)

    #####
    def create_ssh_client(self):
        self.ssh_client = create_ssh_client(self.config.remote_server, self.config.remote_port, self.config.remote_user)


#####
class AnvilTool(object):

    cfg = ConfigWrapper

    #####
    def __init__(self, config = ConfigWrapper):
        super(AnvilTool, self).__init__()
        self.cfg = config

#####
class SourceSync(AnvilTool):
    """Handles the syncing of changes to local source code up to the build server.
    Also creates the custom gradle.properties file that is synced."""

    def __init__(self, config=ConfigWrapper):
        super(SourceSync, self).__init__(config)

    #####
    def md5(self, str):
        return hashlib.md5(str).hexdigest()

    #####
    def md5file(self, fname):
        md5 = hashlib.md5()
        with open(fname, 'rb') as f:
            while True:
                data = f.read(4096)
                if not data:
                    break
                md5.update(data)
        return md5.hexdigest()

    #####
    def rsync_cmd(self):
        sshPort = 'ssh -p {}'.format(self.cfg.config.remote_port)
        cmd = ["rsync", "-zP", "-e", sshPort]
        return cmd

    #####
    def rsync_remote_path(self, remoteFileDir):
        return '{}@{}:{}'.format(self.cfg.config.remote_user, self.cfg.config.remote_server, remoteFileDir)

    #####
    def sync_project_source(self):
        #TODO Logic for custom public key
        dest = self.rsync_remote_path(self.cfg.dest_path)

        ## Build the rsync command
        rsync = self.rsync_cmd()
        rsync.append("-r")
        for file in self.cfg.config.exclude_files:
           rsync.append('--exclude={}'.format(file))
        for file in self.cfg.config.exclude_from_files:
            rsync.append("--exclude-from={}{}".format(self.cfg.local_path, file))
        rsync.append(self.cfg.local_path)
        rsync.append(dest)
        ## Execute. #TODO Interpret the outcome of rsync
        subprocess.call(rsync)
        # print rsync

    #####
    def generateGradleProps(self):
        g = GradleProperties(prepare_path(self.cfg.config.gradle_properties_path_local))
        g.removeArray(self.cfg.config.gradle_properties_remove)
        g.addDict(self.cfg.config.gradle_properties_add)
        return g.generate()

    #####
    def generateLocalProps(self):
        out = GradleProperties.HEADER
        for key, val in self.cfg.config.gradle_local_properties_contents.iteritems():
            out = "{}{}={}\n".format(out, key, val)
        return out

    #####
    def generateAndSyncFile(self, contents="", filename=""):
        localFilepath = "{}{}/{}".format(self.cfg.local_path, ANVIL_DIR_NAME, filename)
        if os.path.exists(localFilepath):
            newMd5 = self.md5(contents)
            oldMd5 = self.md5file(localFilepath)
            if newMd5 == oldMd5:
                return
        with open(localFilepath, 'w') as f:
            f.write(contents)
        destFilename = "{}{}".format(self.cfg.dest_path, filename)
        dest = self.rsync_remote_path(destFilename)
        rsync = self.rsync_cmd()
        rsync.append(localFilepath)
        rsync.append(dest)
        ## Execute. #TODO interpret outcome of rsync
        subprocess.call(rsync)

    #####
    def update_gradle_properties(self):
        newProps = self.generateGradleProps()
        self.generateAndSyncFile(newProps, self.cfg.config.gradle_properties_path_remote)

    #####
    def update_local_properties(self):
        localProps = self.generateLocalProps()
        self.generateAndSyncFile(localProps, self.cfg.config.gradle_local_properties_filename)


#####
class SourceBuilder(AnvilTool):
    """Handles execution of the source build command and retrieval of the console output."""

    #####
    def __init__(self, config=ConfigWrapper):
        super(SourceBuilder, self).__init__(config)

    #####
    def execute_remote_command(self, cmd=""):
        self.cfg.create_ssh_client()
        stdin, stdout, stderr = self.cfg.ssh_client.exec_command(cmd)
        for line in stdout:
            print 'O: ' + line.strip('\n')
        for line in stderr:
            print 'E: ' + line.strip('\n')
            self.cfg.ssh_client.close()

    #####
    def build_project(self):
        cmd = "{}{} -p {} {}".format(self.cfg.dest_path, self.cfg.config.gradle_build_wrapper_file,
                                     self.cfg.dest_path, self.cfg.config.gradle_build_wrapper_task)
        self.execute_remote_command(cmd)


#####
class FilePuller(AnvilTool):

    scp_client = SCPClient

    #####
    def __init__(self, config=ConfigWrapper):
        super(FilePuller, self).__init__(config)
        self.cfg.create_ssh_client()
        self.scp_client = SCPClient(self.cfg.ssh_client.get_transport())

    #####
    def pull_file(self, remote_filename="", local_filename=""):
        if os.path.exists(local_filename):
            os.remove(local_filename)
        print "\nRemote file: {}\nLocal destination: {}".format(remote_filename, local_filename)
        self.scp_client.get(remote_filename, local_filename)
        if os.path.exists(local_filename):
            print "File pulled!"
        else:
            print "Error pulling file."

    #####
    def get_result(self):
        remote_filename = "{}{}{}".format(self.cfg.dest_path, self.cfg.config.remote_result_dir,
                                          self.cfg.config.remote_result_file)
        local_filename = "{}{}/{}".format(self.cfg.local_path, ANVIL_DIR_NAME, self.cfg.config.remote_result_file)
        self.pull_file(remote_filename, local_filename)


#####
# RUNTIME
#####
config = AnvilConfig(CONFIG_FILE)
configWrapper = ConfigWrapper(config)

sync = SourceSync(configWrapper)
sync.sync_project_source()
sync.update_gradle_properties()
sync.update_local_properties()

build = SourceBuilder(configWrapper)
build.build_project()

pull = FilePuller(configWrapper)
pull.get_result()
