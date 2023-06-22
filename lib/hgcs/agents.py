import os
import sys
import errno
import shutil
import time
import re

import htcondor

#===============================================================

# Get main directory path
_MAIN_DIR = os.path.join( os.path.dirname(__file__), '..' )

# Setup lib path
_LIB_PATH = os.path.join( _MAIN_DIR, 'lib' )
sys.path.insert(0, _LIB_PATH)

from hgcs.utils import ThreadBase, MySchedd, global_lock    # noqa: E402

#===============================================================

def get_condor_job_id(job):
    ClusterId = job.get('ClusterId')
    ProcId = job.get('ProcId')
    return '{0}.{1}'.format(ClusterId, ProcId)

#===============================================================

class LogRetriever(ThreadBase):

    projection = [
            'ClusterId', 'ProcId', 'JobStatus',
            'Iwd', 'Err', 'Out', 'UserLog',
            'SUBMIT_UserLog', 'SUBMIT_TransferOutputRemaps',
        ]

    requirements = (
                    'isString(SUBMIT_UserLog) '
                    '&& LeaveJobInQueue isnt false '
                    '&& ( JobStatus == 4 '
                    '|| JobStatus == 3 ) '
                )

    def __init__(self, flush_period = 86400, retrieve_mode='copy', **kwarg):
        ThreadBase.__init__(self, **kwarg)
        if flush_period is None:
            self.flush_period = 86400
        else:
            self.flush_period = flush_period
        self.retrieve_mode = retrieve_mode

    def run(self):
        self.logger.debug('startTimestamp: {0}'.format(self.startTimestamp))
        already_handled_job_id_set = set()
        last_flush_timestamp = time.time()
        while True:
            self.logger.info('run starts')
            if time.time() > last_flush_timestamp + self.flush_period:
                last_flush_timestamp = time.time()
                already_handled_job_id_set = set()
                self.logger.info('flushed already_handled_job_id_set')
            n_try = 999
            for i_try in range(1, n_try + 1):
                try:
                    schedd = MySchedd()
                    break
                except RuntimeError as e:
                    if i_try < n_try:
                        self.logger.warning('{0} . Retry...'.format(e))
                        time.sleep(3)
                    else:
                        self.logger.error('{0} . No more retry. Exit'.format(e))
                        return
            for job in schedd.xquery(constraint=self.requirements,
                                        projection=self.projection):
                job_id = get_condor_job_id(job)
                if job_id in already_handled_job_id_set:
                    continue
                self.logger.debug('to retrieve for condor job {0}'.format(job_id))
                if self.retrieve_mode == 'symlink':
                    self.via_system(job, symlink_mode=True)
                elif self.retrieve_mode == 'copy':
                    retVal = self.via_system(job)
                    if retVal:
                        already_handled_job_id_set.add(job_id)
                elif self.retrieve_mode == 'condor':
                    self.via_condor_retrieve(job)
            n_try = 3
            for i_try in range(1, n_try + 1):
                try:
                    schedd.edit(list(already_handled_job_id_set), 'LeaveJobInQueue', 'false')
                except RuntimeError:
                    if i_try < n_try:
                        self.logger.warning('failed to edit job {0} . Retry: {1}'.format(job_id, i_try))
                        time.sleep(1)
                    else:
                        self.logger.warning('failed to edit job {0} . Skipped...'.format(job_id))
                else:
                    already_handled_job_id_set.clear()
                    break
            self.logger.info('run ends')
            time.sleep(self.sleep_period)

    def via_system(self, job, symlink_mode=False):
        retVal = True
        job_id = get_condor_job_id(job)
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
        if not dest_log:
            self.logger.debug('{0} has no attribute of spool. Skipped...'.format(job_id))
            return True
        for _m in transfer_remap_list:
            match = re.search('([a-zA-Z0-9_.\-]+)=([a-zA-Z0-9_.\-/]+)', _m)
            if match:
                name = match.group(1)
                dest_path = os.path.normpath(match.group(2))
                if name == src_log_name:
                    dest_log = dest_path
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


class CleanupDelayer(ThreadBase):

    requirements = (
        'SUBMIT_UserLog is undefined '
        '&& LeaveJobInQueue is false '
        '&& ( member(JobStatus, {1,2,5,6,7}) )'
    )
    ad_LeaveJobInQueue_template = (
        '( time() - EnteredCurrentStatus ) < {delay_time} '
        )

    def __init__(self, sleep_period=60, delay_time=7200):
        ThreadBase.__init__(self)
        self.delay_time = delay_time

    def run(self):
        self.logger.debug('startTimestamp: {0}'.format(self.startTimestamp))
        while True:
            self.logger.info('run starts')
            n_try = 999
            for i_try in range(1, n_try + 1):
                try:
                    schedd = MySchedd()
                    break
                except RuntimeError as e:
                    if i_try < n_try:
                        self.logger.warning('{0} . Retry...'.format(e))
                        time.sleep(3)
                    else:
                        self.logger.error('{0} . No more retry. Exit'.format(e))
                        return
            # for job in schedd.xquery(constraint=self.requirements):
            #     job_id = get_condor_job_id(job)
            #     self.logger.debug('to adjust LeaveJobInQueue of condor job {0}'.format(job_id))
            job_id_list = [ get_condor_job_id(job) for job in schedd.xquery(constraint=self.requirements) ]
            n_jobs = len(job_id_list)
            n_try = 3
            for i_try in range(1, n_try + 1):
                try:
                    schedd.edit(job_id_list, 'LeaveJobInQueue',
                                    self.ad_LeaveJobInQueue_template.format(delay_time=self.delay_time))
                except RuntimeError:
                    if i_try < n_try:
                        self.logger.warning('failed to edit {0} jobs . Retry: {1}'.format(n_jobs, i_try))
                        time.sleep(1)
                    else:
                        self.logger.warning('failed to edit {0} jobs . Skipped...'.format(n_jobs))
                else:
                    self.logger.debug('adjusted LeaveJobInQueue of {0} condor jobs '.format(n_jobs))
                    break
            self.logger.info('run ends')
            time.sleep(self.sleep_period)


class SDFFetcher(ThreadBase):

    projection = [
            'ClusterId', 'ProcId', 'JobStatus',
            'UserLog', 'SUBMIT_UserLog',
            'sdfPath', 'sdfCopied',
        ]

    requirements = (
                    '(isUndefined(sdfCopied) || sdfCopied == 0) '
                    '&& isString(sdfPath) '
                )

    def __init__(self, flush_period=86400, limit=6000, **kwarg):
        ThreadBase.__init__(self, **kwarg)
        if flush_period is None:
            self.flush_period = 86400
        else:
            self.flush_period = flush_period
        if limit is not None:
            self.limit = limit
        else:
            self.limit = 6000

    def run(self):
        self.logger.debug('startTimestamp: {0}'.format(self.startTimestamp))
        already_handled_job_id_set = set()
        last_flush_timestamp = time.time()
        while True:
            self.logger.info('run starts')
            if time.time() > last_flush_timestamp + self.flush_period:
                last_flush_timestamp = time.time()
                already_handled_job_id_set = set()
                self.logger.info('flushed already_handled_job_id_set')
            n_try = 999
            for i_try in range(1, n_try + 1):
                try:
                    schedd = MySchedd()
                    break
                except RuntimeError as e:
                    if i_try < n_try:
                        self.logger.warning('{0} . Retry...'.format(e))
                        time.sleep(3)
                    else:
                        self.logger.error('{0} . No more retry. Exit'.format(e))
                        return
            already_sdf_copied_job_id_set = set()
            failed_and_to_skip_sdf_copied_job_id_set = set()
            try:
                jobs_iter = schedd.xquery(constraint=self.requirements,
                                            projection=self.projection,
                                            limit=self.limit)
                for job in jobs_iter:
                    job_id = get_condor_job_id(job)
                    if job_id in already_handled_job_id_set:
                        continue
                    self.logger.debug('to copy sdf for condor job {0}'.format(job_id))
                    retVal = self.via_system(job)
                    if retVal is True:
                        already_sdf_copied_job_id_set.add(job_id)
                    elif retVal is False:
                        failed_and_to_skip_sdf_copied_job_id_set.add(job_id)
            except RuntimeError as e:
                self.logger.error('Failed to query jobs. Exit. RuntimeError: {0} '.format(e))
            else:
                n_try = 3
                for i_try in range(1, n_try + 1):
                    try:
                        schedd.edit(list(already_sdf_copied_job_id_set), 'sdfCopied', '1')
                    except RuntimeError:
                        if i_try < n_try:
                            self.logger.warning('failed to edit job {0} . Retry: {1}'.format(job_id, i_try))
                            time.sleep(1)
                        else:
                            self.logger.warning('failed to edit job {0} . Skipped...'.format(job_id))
                    else:
                        already_handled_job_id_set.update(already_sdf_copied_job_id_set)
                        already_sdf_copied_job_id_set.clear()
                        break
                n_try = 3
                for i_try in range(1, n_try + 1):
                    try:
                        schedd.edit(list(failed_and_to_skip_sdf_copied_job_id_set), 'sdfCopied', '2')
                    except RuntimeError:
                        if i_try < n_try:
                            self.logger.warning('failed to edit job {0} . Retry: {1}'.format(job_id, i_try))
                            time.sleep(1)
                        else:
                            self.logger.warning('failed to edit job {0} . Skipped...'.format(job_id))
                    else:
                        already_handled_job_id_set.update(failed_and_to_skip_sdf_copied_job_id_set)
                        failed_and_to_skip_sdf_copied_job_id_set.clear()
                        break
            self.logger.info('run ends')
            time.sleep(self.sleep_period)

    def via_system(self, job):
        retVal = True
        job_id = get_condor_job_id(job)
        src_path = job.get('sdfPath')
        dest_log = job.get('SUBMIT_UserLog')
        if not dest_log:
            dest_log = job.get('UserLog')
        if not dest_log:
            self.logger.debug('{0} has no valid SUBMIT_UserLog nor UserLog. Skipped...'.format(job_id))
            return True
        dest_dir = os.path.dirname(dest_log)
        dest_filename = re.sub(r'.log$', '.jdl', os.path.basename(dest_log))
        dest_path = os.path.normpath(os.path.join(dest_dir, dest_filename))
        if not os.path.isfile(src_path):
            retVal = False
            self.logger.error('{0} is not a regular file. Skipped...'.format(src_path))
        if not dest_path:
            retVal = False
            self.logger.error('no destination path for {0} . Skipped...'.format(src_path))
        if retVal is True:
            if os.path.isfile(dest_path):
                self.logger.debug('{0} file already exists. Skipped...'.format(dest_path))
                return True
            try:
                shutil.copy2(src_path, dest_path)
                if os.path.isfile(dest_path):
                    os.chmod(dest_path, 0o644)
                    self.logger.debug('{0} copy made'.format(dest_path))
                else:
                    retVal = None
                    self.logger.error('{0} made but not found'.format(dest_path))
            except OSError as e:
                if e.errno == errno.EEXIST:
                    self.logger.debug('{0} file already exists. Skipped...'.format(dest_path))
                else:
                    retVal = None
                    self.logger.error(e)
            except Exception as e:
                retVal = None
                self.logger.error(e)
        return retVal


class XJobCleaner(ThreadBase):

    requirements_template = (
                    'JobStatus =?= 3 '
                    '&& time() - EnteredCurrentStatus >= {grace_period} '
                )

    def __init__(self, grace_period=86400, **kwarg):
        ThreadBase.__init__(self, **kwarg)
        if grace_period is None:
            self.grace_period = 86400
        else:
            self.grace_period = grace_period

    def run(self):
        self.logger.debug('startTimestamp: {0}'.format(self.startTimestamp))
        while True:
            self.logger.info('run starts')
            n_try = 999
            for i_try in range(1, n_try + 1):
                try:
                    schedd = MySchedd()
                    break
                except RuntimeError as e:
                    if i_try < n_try:
                        self.logger.warning('{0} . Retry...'.format(e))
                        time.sleep(3)
                    else:
                        self.logger.error('{0} . No more retry. Exit'.format(e))
                        return
            try:
                requirements = self.requirements_template.format(grace_period=int(self.grace_period))
                self.logger.debug('try to remove-x jobs')
                with global_lock:
                    act_ret = schedd.act(htcondor.JobAction.RemoveX, requirements)
            except RuntimeError as e:
                self.logger.error('Failed to remove-x jobs. Exit. RuntimeError: {0} '.format(e))
            else:
                self.logger.debug('act return : {act_ret}'.format(act_ret=str(dict(act_ret))))
            self.logger.info('run ends')
            time.sleep(self.sleep_period)
