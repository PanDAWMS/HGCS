import os
import sys
import re

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

#===============================================================

# dummy section class
class _SectionClass(object):
    def __init__(self):
        pass


# config class
class ConfigClass(object):
    def __init__(self, config_file=None):
        # get ConfigParser
        tmpConf = configparser.ConfigParser()
        # default and env variable for config file path
        configPath_specified = os.path.normpath(config_file)
        configEnvVar = 'HGCS_CONFIG_PATH'
        configPath_default = '/etc/hgcs.cfg'
        if configPath_specified:
            configPath = configPath_specified
        elif configEnvVar in os.environ:
            configPath = os.path.normpath(os.environ[configEnvVar])
        else:
            configPath = configPath_default
        # read
        try:
            tmpConf.read(configPath)
        except Exception as e:
            print('Failed to read config file from {0}: {1}'.format(configPath, e))
            raise e
            return False
        # loop over all sections
        for tmpSection in tmpConf.sections():
            # read section
            tmpDict = tmpConf[tmpSection]
            # make section class
            tmpSelf = _SectionClass()
            # update module dict
            setattr(self, tmpSection, tmpSelf)
            # expand all values
            for tmpKey, tmpVal in tmpDict.items():
                # use env vars
                if tmpVal.startswith('$'):
                    tmpMatch = re.search('\$\{*([^\}]+)\}*', tmpVal)
                    envName = tmpMatch.group(1)
                    if envName not in os.environ:
                        raise KeyError('{0} in the cfg is an undefined environment variable.'.format(envName))
                    tmpVal = os.environ[envName]
                # convert string to bool/int
                if tmpVal == 'True':
                    tmpVal = True
                elif tmpVal == 'False':
                    tmpVal = False
                elif tmpVal == 'None':
                    tmpVal = None
                elif re.match('^\d+$', tmpVal):
                    tmpVal = int(tmpVal)
                elif '\n' in tmpVal:
                    tmpVal = tmpVal.split('\n')
                    # remove empty
                    tmpVal = [x.strip() for x in tmpVal if x.strip()]
                # update dict
                setattr(tmpSelf, tmpKey, tmpVal)
