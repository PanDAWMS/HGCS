"""
main executable of HGCS
"""

import os
import sys
import inspect
import argparse
import logging

# # Get main directory path
# _MAIN_DIR = os.path.join( os.path.dirname(__file__), '..' )
#
# # Setup lib path
# _LIB_PATH = os.path.join( _MAIN_DIR, 'lib' )
# sys.path.insert(0, _LIB_PATH)

from hgcs import hgcs_config    # noqa: E402
from hgcs import agents    # noqa: E402
from hgcs import utils    # noqa: E402

#===============================================================

LOG_LEVEL_MAP = {
    'ERROR': logging.ERROR,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
}

#===============================================================

def main():
    """
    main function
    """
    # command argparse
    oparser = argparse.ArgumentParser(prog='hgcs', add_help=True)
    # subparsers = oparser.add_subparsers()
    oparser.add_argument('-c', '--config', action='store',
                            dest='config', metavar='<file>',
                            help='Configuration file')
    oparser.add_argument('-F', '--foregroudlog', action='store_true',
                            dest='foregroudlog',
                            help='Print logs to foregroud')
    # start parsing
    if len(sys.argv) == 1:
        oparser.print_help()
        sys.exit(1)
    arguments = oparser.parse_args(sys.argv[1:])
    # config file option
    if os.path.isfile(arguments.config):
        config_file_path = arguments.config
    else:
        print(f'Invalid configuration file: {arguments.config}')
        sys.exit(1)
    # defaults
    log_file = '/tmp/hgcs.log'
    log_level = 'DEBUG'
    logger_format_colored = True
    # load config
    try:
        config = hgcs_config.ConfigClass(config_file_path)
    except IOError as exc:
        print(f'IOError: {exc}')
        sys.exit(1)
    except Exception as exc:
        print(f'Cannot load conifg: {exc}')
        sys.exit(1)
    # handle master part of config
    try:
        master_section = getattr(config, 'Master')
    except AttributeError:
        pass
    else:
        if getattr(master_section, 'log_file', False):
            log_file = getattr(master_section, 'log_file')
            logger_format_colored = False
        if getattr(master_section, 'log_level', False):
            log_level = getattr(master_section, 'log_level')
    # case for logs to foregroud stderr
    if arguments.foregroudlog:
        log_file = None
        logger_format_colored = True
    # add threads of agents to run
    thread_list = []
    for name, class_obj in inspect.getmembers(agents,
        lambda m: inspect.isclass(m) and m.__module__ == 'hgcs.agents'):
        if hasattr(config, name):
            section = getattr(config, name)
            if getattr(section, 'enable', False):
                param_dict = {
                    'sleep_period': getattr(section, 'sleep_period'),
                    'flush_period': getattr(section, 'flush_period', None),
                    'grace_period': getattr(section, 'grace_period', None),
                    'limit': getattr(section, 'limit', None),
                    }
                agent_instance = class_obj(**param_dict)
                utils.setup_logger(agent_instance.logger,
                                    pid=agent_instance.get_pid,
                                    colored=logger_format_colored,
                                    to_file=log_file)
                logging_log_level = LOG_LEVEL_MAP.get(log_level, logging.ERROR)
                agent_instance.logger.setLevel(logging_log_level)
                thread_list.append(agent_instance)
    # run threads
    for thr in thread_list:
        print(f'Start thread of agent {thr.__class__.__name__}')
        thr.start()

#===============================================================

if __name__ == '__main__':
    main()
