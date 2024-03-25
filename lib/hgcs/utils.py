"""
common utilities of HGCS
"""

import logging
import os
import threading
import time

from threading import get_ident

import htcondor


# ===============================================================

global_lock = threading.Lock()

# ===============================================================

# ===============================================================

LOG_LEVEL_MAP = {
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

# ===============================================================


def setup_logger(logger, pid=None, colored=True, to_file=None):
    """
    set up the logger
    """
    if to_file is not None:
        hdlr = logging.FileHandler(to_file)
        colored = False
    else:
        hdlr = logging.StreamHandler()

    def emit_decorator(orig_func):
        def func(*args):
            _fstr = f"[%(asctime)s %(levelname)s]({pid})(%(name)s.%(funcName)s) %(message)s"
            format_str = _fstr
            if colored:
                levelno = args[0].levelno
                if levelno >= logging.CRITICAL:
                    color = "\033[35;1m"
                elif levelno >= logging.ERROR:
                    color = "\033[31;1m"
                elif levelno >= logging.WARNING:
                    color = "\033[33;1m"
                elif levelno >= logging.INFO:
                    color = "\033[32;1m"
                elif levelno >= logging.DEBUG:
                    color = "\033[36;1m"
                else:
                    color = "\033[0m"
                format_str = f"{color}{_fstr}\033[0m"
            formatter = logging.Formatter(format_str)
            hdlr.setFormatter(formatter)
            return orig_func(*args)

        return func

    hdlr.emit = emit_decorator(hdlr.emit)
    logger.addHandler(hdlr)


# ===============================================================


class ThreadBase(threading.Thread):
    """
    base class of thread to run HGCS agents
    """

    def __init__(self, sleep_period=60, **kwargs):
        threading.Thread.__init__(self)
        self.os_pid = os.getpid()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.sleep_period = sleep_period
        self.start_timestamp = time.time()
        self.logger_format_colored = kwargs.get("logger_format_colored")
        self.log_level = kwargs.get("log_level")
        self.log_file = kwargs.get("log_file")
    
    def set_logger(self):
        setup_logger(self.logger, pid=self.get_pid(), colored=self.logger_format_colored, to_file=self.log_file)
        logging_log_level = LOG_LEVEL_MAP.get(self.log_level, logging.ERROR)
        self.logger.setLevel(logging_log_level)

    def get_pid(self):
        """
        get unique thread identifier including process ID (from OS) and thread ID (from python)
        """
        return f"{self.os_pid}-{get_ident()}"

    def run(self):
        """
        run the agent
        """
        pass


class MySchedd(htcondor.Schedd):
    """
    Schedd class in singleton
    """

    __instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls.__instance, cls):
            cls.__instance = super(MySchedd, cls).__new__(cls, *args, **kwargs)
        return cls.__instance
