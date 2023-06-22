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
        tmp_conf = configparser.ConfigParser()
        # default and env variable for config file path
        config_path_specified = os.path.normpath(config_file)
        config_env_var = 'HGCS_CONFIG_PATH'
        config_path_default = '/etc/hgcs.cfg'
        if config_path_specified:
            config_path = config_path_specified
        elif config_env_var in os.environ:
            config_path = os.path.normpath(os.environ[config_env_var])
        else:
            config_path = config_path_default
        # read
        try:
            tmp_conf.read(config_path)
        except Exception as exc:
            print(f'Failed to read config file from {config_path}: {exc}')
            raise exc
        # loop over all sections
        for tmp_section in tmp_conf.sections():
            # read section
            tmp_dict = tmp_conf[tmp_section]
            # make section class
            tmp_self = _SectionClass()
            # update module dict
            setattr(self, tmp_section, tmp_self)
            # expand all values
            for tmp_key, tmp_val in tmp_dict.items():
                # use env vars
                if tmp_val.startswith('$'):
                    tmp_match = re.search('\$\{*([^\}]+)\}*', tmp_val)
                    env_name = tmp_match.group(1)
                    if env_name not in os.environ:
                        raise KeyError(f'{env_name} in config is undefined env variable')
                    tmp_val = os.environ[env_name]
                # convert string to bool/int
                if tmp_val.lower() == 'true':
                    tmp_val = True
                elif tmp_val.lower() == 'false':
                    tmp_val = False
                elif tmp_val.lower() == 'none':
                    tmp_val = None
                elif re.match('^\d+$', tmp_val):
                    tmp_val = int(tmp_val)
                elif '\n' in tmp_val:
                    tmp_val = tmp_val.split('\n')
                    # remove empty
                    tmp_val = [x.strip() for x in tmp_val if x.strip()]
                # update dict
                setattr(tmp_self, tmp_key, tmp_val)
