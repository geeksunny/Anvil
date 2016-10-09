import configparser
import StringIO

_dummy = "dummy"

#####
class GradleProperties(object):

    HEADER = "# auto-generated gradle.properties"
    config = None

    #####
    def __init__(self, filename):
        self.config = configparser.ConfigParser(strict=False,interpolation=None)
        with open(filename) as f:
            vfilestr = '[{}]\n{}'.format(_dummy, f.read())
            vfile = StringIO.StringIO(vfilestr)
            self.config.read_file(vfile)

    #####
    def addDict(self, dict):
        for key, val in dict.iteritems():
            self.add(key, val)

    #####
    def add(self, key, val):
        self.config.set(_dummy, key, val)

    #####
    def removeArray(self, array):
        for key in array:
            self.remove(key)

    #####
    def remove(self, key):
        self.config.remove_option(_dummy, key)

    #####
    def generate(self):
        out = self.HEADER
        for key, val in self.config[_dummy].iteritems():
            out = "{}\n{}={}".format(out, key, val)
        return out

# addProps = {"sdk.dir":"/usr/lib/android-sdk", "test_val":"neatoSK33t0"}
# gradle = GradleProperties("~/.gradle/gradle.properties")
# gradle.addDict(addProps)
# print gradle.generate()