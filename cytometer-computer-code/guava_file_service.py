import os
import shutil
from time import sleep, time
from datetime import datetime, date
import logging
from threading import Thread

local_path = "C:\\Users\\User\\Documents"
local_backup_path = "C:\\Users\\User\\guava-local-backup"
atlas_path = "Z:\\raw-cytometer-data"

logging.basicConfig(filename=local_path + '/local2atlas_logs/{}.log'.format(str(datetime.now()).replace(' ','_').replace(':','-')), filemode='w', level=logging.INFO)
logging.info('starting new log')

def list_local_fcs_files():
    local_fcs_files = {'guava-fcs-3.0':[], 'guava-autosave-FCS-2.0':[], 'guava-xml':[]}
    for fname in os.listdir(local_path):
        if fname.endswith('.FCS'):
            local_fcs_files['guava-autosave-FCS-2.0'].append((local_path,fname))
        if fname.endswith('.fcs'):
            local_fcs_files['guava-fcs-3.0'].append((local_path,fname))
        if fname.endswith('.xml'):
            local_fcs_files['guava-xml'].append((local_path,fname))
    return local_fcs_files

def extract_date_info_from_name(fname):
    try:
        file_yr = int(fname.split('-')[0])
        file_mo = int(fname.split('-')[1])
        file_day = int(fname.split('-')[2].split('_')[0])
        return file_yr, file_mo, file_day
    except:
        return None, None, None

def guavafilename2datetime(fname):
    yr = int(fname.split('-')[0])
    mo = int(fname.split('-')[1])
    dy = int(fname.split('-')[2].split('_')[0])
    hr = int(fname.split('_')[-1].split('-')[0])
    mn = int(fname.split('_')[-1].split('-')[1])
    sec = int(fname.split('_')[-1].split('-')[2][:2])
    if 'pm' in fname:
        if hr < 12:
            hr += 12
    if 'am' in fname and hr == 12:
        hr = 0
    d = datetime(yr,mo,dy,hr,mn,sec)
    return d

class Service(Thread):
    def __init__(self):
        super().__init__()
        self.status = 'ready'
        self.raw_file = None
        self.acq_start_time = None
    def run(self):
        while True:
            # list fcs files on the local folder
            local_fcs_files = list_local_fcs_files()
            # if we should handle onoing acquisition, check if new file corresponds
            # if yes, mark the acquisition has finished
            # only when retrieved by an external request should the status go back to ready, allowing regular backup
            # means that if no ones retrieves the file, we can have issues
            if self.status == 'ongoing':
                dfirst = None
                fpathfirst = None
                for local_dir,fname in local_fcs_files['guava-fcs-3.0']:
                    d = guavafilename2datetime(fname)
                    if d > self.acq_start_time:
                        if dfirst is None:
                            dfirst = d
                            fpathfirst = os.path.join(local_dir,fname)
                        else:
                            if d < dfirst:
                                dfirst = d
                                fpathfirst = os.path.join(local_dir,fname)
                if dfirst is not None:
                    self.raw_file = fpathfirst
                    self.status = 'finished'
            # if not handling an ongoing acquistion, regular backup strategy: loop on fcs files, check if on atlas, if not try to copy
            if self.status == 'ready':
                for fcs_format,fcs_files in local_fcs_files.items():
                    for local_dir,fname in fcs_files:
                        # extract / compute info about the file
                        file_yr, file_mo, file_day = extract_date_info_from_name(fname)
                        if file_yr is not None:
                            src_fpth = os.path.join(local_dir,fname)
                            trg_dir = os.path.join(atlas_path,fcs_format,'{}-{}'.format(file_yr, file_mo))
                            trg_local_dir = os.path.join(local_backup_path,fcs_format,'{}-{}'.format(file_yr, file_mo))
                            # do the stuff that can fail in a try / except catching everything and logging it
                            try:
                                if not os.path.exists(trg_dir):
                                    os.mkdir(trg_dir)
                                trg_fpth = os.path.join(trg_dir,fname)
                                if not os.path.isfile(trg_fpth):
                                    logging.info('{} | trying to copy {} to atlas (target path = {})'.format(datetime.now(),fname,trg_fpth))
                                    shutil.copy2(src_fpth, trg_fpth + '.part')
                                    os.rename(trg_fpth + '.part', trg_fpth)
                                else:
                                    if not os.path.exists(trg_local_dir):
                                        os.mkdir(trg_local_dir)
                                    trg_local_fpth = os.path.join(trg_local_dir, fname)
                                    logging.info('{} | {} already in atlas (target path = {})'.format(datetime.now(),fname,trg_fpth))
                                    logging.info('{} | {} trying to locally backup (target path = {})'.format(datetime.now(),fname,trg_local_fpth))
                                    shutil.move(src_fpth, trg_local_fpth)
                            except BaseException as e:
                                logging.error('Something went wrong (error: {})'.format(e))
                            sleep(0.3)
            #
            logging.info('{} - still alive'.format(datetime.now()))
            sleep(20)
    def declare_ongoing_acquisition(self):
        self.status = 'ongoing'
        self.acq_start_time = datetime.now()
