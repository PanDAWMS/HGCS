import os
import sys

try:
    import configparser
except ImportError:
    import ConfigParser as configparser


# get ConfigParser
tmpConf = configparser.ConfigParser()

# env variable for config file path
configEnvVar = 'HGCS_CONFIG_PATH'
configPath_default = None #FIXME
if configEnvVar in os.environ:
    configPath = os.path.normpath(os.environ[configEnvVar])
else:
    configPath = configPath_default

# read
tmpConf.read(configPath)

# dummy section class
class _SectionClass:
    def __init__(self):
        pass

# loop over all sections
for tmpSection in tmpConf.sections():
    # read section
    tmpDict = getattr(tmpConf, tmpSection)
    # make section class
    tmpSelf = _SectionClass()
    # update module dict
    sys.modules[__name__].setattr(tmpSection, tmpSelf)
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
