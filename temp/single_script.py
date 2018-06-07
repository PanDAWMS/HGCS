import os
import sys
import errno
import shutil

import time
import re
import threading
import logging

try:
    from threading import get_ident
except ImportError:
    from thread import get_ident

import htcondor
import classad

#===============================================================

def setupLogger(logger, pid=None, colored=True):
    logger.setLevel(logging.DEBUG)
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


def get_condor_job_id(job):
    ClusterId = job.get('ClusterId')
    ProcId = job.get('ProcId')
    return '{0}.{1}'.format(ClusterId, ProcId)

#===============================================================

class Singleton(type):
    def __init__(cls, name, bases, dct):
        cls.__instance = None
        type.__init__(cls, name, bases, dct)
    def __call__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = type.__call__(cls, *args,**kwargs)
        return cls.__instance


class ThreadBase(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.os_pid = os.getpid()
        self.logger = logging.getLogger(self.__class__.__name__)
        setupLogger(self.logger, pid=self.get_pid, colored=False)
        self.startTimestamp = time.time()

    @property
    def get_pid(self):
        return '{0}-{1}'.format(self.os_pid, get_ident())


class MySchedd(htcondor.Schedd):
    __metaclass__ = Singleton


class LogRetriever(ThreadBase):
    def __init__(self, retrieve_mode='copy', sleep_period=60, flush_period=86400):
        ThreadBase.__init__(self)
        self.retrieve_mode = retrieve_mode
        self.sleep_period = sleep_period
        self.flush_period = flush_period

    def run(self):
        self.logger.debug('startTimestamp: {0}'.format(self.startTimestamp))
        already_retrived_job_id_set = set([])
        last_flush_timestamp = time.time()
        while True:
            self.logger.info('run starts')
            if time.time() > last_flush_timestamp + self.flush_period:
                last_flush_timestamp = time.time()
                already_retrived_job_id_set = set([])
                self.logger.debug('flushed already_retrived_job_id_set')
            schedd = MySchedd()
            requirements = (
                'JobStatus == 4 '
                '|| JobStatus == 3 '
            )
            for job in schedd.xquery(requirements=requirements):
                job_id = get_condor_job_id(job)
                if job_id in already_retrived_job_id_set:
                    continue
                self.logger.debug('to retrieve for condor job {0}'.format(job_id))
                if self.retrieve_mode == 'symlink':
                    self.via_system(job, symlink_mode=True)
                elif self.retrieve_mode == 'copy':
                    retVal = self.via_system(job)
                    if retVal:
                        already_retrived_job_id_set.add(job_id)
                elif self.retrieve_mode == 'condor':
                    self.via_condor_retrieve(job)
            try:
                schedd.edit(list(already_retrived_job_id_set), 'LeaveJobInQueue', 'false')
            except RuntimeError:
                self.logger.warning('failed to edit job {0} . Skipped...'.format(job_id))
            self.logger.info('run ends')
            time.sleep(self.sleep_period )

    def via_system(self, job, symlink_mode=False):
        retVal = True
        src_dir = job.get('Iwd')
        src_err_name = job.get('Err')
        src_out_name = job.get('Out')
        src_log_name = job.get('UserLog')
        src_err = os.path.join(src_dir, src_err_name)
        src_out = os.path.join(src_dir, src_out_name)
        src_log = os.path.join(src_dir, src_log_name)
        dest_err = None
        dest_out = None
        dest_log = job.get('SUBMIT_UserLog')
        transfer_remap_list = str(job.get('SUBMIT_TransferOutputRemaps')).split(';')
        for _m in transfer_remap_list:
            match = re.search('([a-zA-Z0-9_.\-]+)=([a-zA-Z0-9_.\-/]+)', _m)
            if match:
                name = match.group(1)
                dest_path = os.path.normpath(match.group(2))
                if name == src_log_name:
                    dest_log = osdest_path
                elif name == src_out_name:
                    dest_out = dest_path
                elif name == src_err_name:
                    dest_err = dest_path
        for src_path, dest_path in zip([src_err, src_out, src_log], [dest_err, dest_out, dest_log]):
            if not os.path.isfile(src_path) or os.path.islink(src_path):
                if job.get('JobStatus') != 4:
                    continue
                retVal = False
                self.logger.error('{0} is not a regular file. Skipped...'.format(src_path))
                continue
            if not dest_path:
                retVal = False
                self.logger.error('no destination path for {0} . Skipped...'.format(src_path))
                continue
            try:
                if symlink_mode:
                    os.symlink(src_path, dest_path)
                    if os.path.islink(dest_path):
                        self.logger.debug('{0} symlink made'.format(dest_path))
                    else:
                        retVal = False
                        self.logger.error('{0} made but not found'.format(dest_path))
                else:
                    shutil.copy2(src_path, dest_path)
                    if os.path.isfile(dest_path):
                        self.logger.debug('{0} copy made'.format(dest_path))
                    else:
                        retVal = False
                        self.logger.error('{0} made but not found'.format(dest_path))
            except OSError as e:
                if e.errno == errno.EEXIST:
                    self.logger.debug('{0} file already exists. Skipped...'.format(dest_path))
                else:
                    retVal = False
                    self.logger.error(e)
            except Exception as e:
                retVal = False
                self.logger.error(e)
        return retVal

    def via_condor_retrieve(self, job):
        pass


def testing():
    """
    Test function
    """
    schedd = MySchedd()
    # for job in schedd.xquery(projection=['ClusterId', 'ProcId', 'JobStatus']):
    #     print(repr(job))
    # requirements = (
    #     'JobStatus == 4 '
    #     '&& User == "atlpan@cern.ch" '
    #     '&& ClusterId == 18769 '
    # )
    # for job in schedd.xquery(requirements=requirements):
    #     print(job.get('ClusterId'), job.get('JobStatus'), job.get('SUBMIT_UserLog', None),  job.get('ffffff', None))
    thr = LogRetriever()
    thr.start()


def main():
    """
    Main function
    """
    pass


if __name__ == '__main__':
    testing()
    main()
