import os
import time
import logging
import threading

try:
    from threading import get_ident
except ImportError:
    from thread import get_ident

import htcondor

#===============================================================

global_lock = threading.Lock()

#===============================================================

def setupLogger(logger, pid=None, colored=True, to_file=None):
    if to_file is not None:
        hdlr = logging.FileHandler(to_file)
        colored = False
    else:
        hdlr = logging.StreamHandler()
    def emit_decorator(fn):
        def func(*args):
            if colored:
                levelno = args[0].levelno
                if(levelno >= logging.CRITICAL):
                    color = '\033[35;1m'
                elif(levelno >= logging.ERROR):
                    color = '\033[31;1m'
                elif(levelno >= logging.WARNING):
                    color = '\033[33;1m'
                elif(levelno >= logging.INFO):
                    color = '\033[32;1m'
                elif(levelno >= logging.DEBUG):
                    color = '\033[36;1m'
                else:
                    color = '\033[0m'
                # formatter = logging.Formatter('{0}%(asctime)s %(levelname)s in %(filename)s:%(funcName)s:%(lineno)d [%(message)s]\033[0m'.format(color))
                formatter = logging.Formatter('{0}[%(asctime)s %(levelname)s]({1})(%(name)s.%(funcName)s) %(message)s\033[0m'.format(color, pid))
            else:
                formatter = logging.Formatter('%(asctime)s %(levelname)s]({0})(%(name)s.%(funcName)s) %(message)s'.format(pid))
            hdlr.setFormatter(formatter)
            return fn(*args)
        return func
    hdlr.emit = emit_decorator(hdlr.emit)
    logger.addHandler(hdlr)

#===============================================================

class ThreadBase(threading.Thread):
    def __init__(self, sleep_period=60, **kwarg):
        threading.Thread.__init__(self)
        self.os_pid = os.getpid()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.sleep_period = sleep_period
        self.startTimestamp = time.time()

    @property
    def get_pid(self):
        return '{0}-{1}'.format(self.os_pid, get_ident())


class MySchedd(htcondor.Schedd):
    __instance = None
    def __new__(cls, *args, **kwargs):
        if not isinstance(cls.__instance, cls):
            cls.__instance = super(MySchedd, cls).__new__(cls, *args, **kwargs)
        return cls.__instance
