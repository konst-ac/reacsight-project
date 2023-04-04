from cytoreactors.design.reactors import reactors
from cytoreactors.design.program import TurbidostatProgram, GrowDiluteProgram, Preculture
from cytoreactors.operate.api.manager import Manager
from time import time, sleep
from threading import Thread
import logging
import pandas as pd
import shutil
import guava2data
from datetime import datetime, date
import os

# just to forbid creation of two sessions
session_created = False

### the main class
class Session():

    def __init__(self, fake_OT2=False, virtual_mode=False, automated_beads = True):
        global session_created
        if session_created:
            raise Exception('Session already running, stop it before starting a new one.')
        self.status = 'created'
        session_created = True
        self.fake_OT2 = fake_OT2
        self.virtual_mode = virtual_mode
        self.manager = Manager(fake_OT2=self.fake_OT2, virtual_mode=self.virtual_mode)
        if self.virtual_mode:
            self.loop_duration_s = 120. / 1000.
        else:
            self.loop_duration_s = 120.
        self.programs = {} # dict indexed by reactor id
        self.loop_counter = 0
        self.sampling_schedule = []
        self.samplings = []

        self.ot2_plate_num = 1
        self.ot2_col = 12

        self.low_volume_no_sampling_safety = False
        self.additional_cytoplate_dilution = False # to dilute 20X more (not needed if OD below 1.0)
        self.keep_tips_between_cytoplate_dilutions = False
        self.guava_num_events = 5000
        self.should_wash = False
        self.waiting_for_guava_data = False
        self.run_thread = None
        self.reactor_ids_to_clean = []
        
        # -----------------------------------------------------
        # NEW STUFF FOR BEADS AUTOMATION 
        # -----------------------------------------------------
        self.automated_beads = automated_beads # if we are running on flasrkr.py, self.automated_beads = True 
        # if not, (running on flaskr_no_beads.py) , self.automated_beads = False
        
        self.sec_schedule = [] # an equivalent of : self.sampling_schedule = []
        self.secs = [] # an equivalent of : self.samplings = []
        self.sec_count = 1
        self.waiting_for_guava_data_sec = False
        self.should_wash_row2 = False 
        
        # -----------------------------------------------------
        # END NEW STUFF 
        # -----------------------------------------------------

    @property
    def programs_with_cytometry(self):
        return {rid:program for rid,program in self.programs.items() if program.active_cytometry}

    # from excel file
    def load_programs(self):
        df_programs = pd.read_excel('description-programs.xlsx')
        for _,df_prog in df_programs.iterrows():
            #
            prec = Preculture(strain_id=df_prog['preculture_strain_id'],
                            strain_name=df_prog['preculture_strain_name'],
                            media=df_prog['preculure_media'])
            # decide on program type based on OD_low and OD_high
            if df_prog['OD_low'] == df_prog['OD_low']:
                prog = TurbidostatProgram(user=df_prog['user'],
                                          campaign=df_prog['campaign'],
                                          short_name=df_prog['short_name'],
                                          description=df_prog['description'],
                                          reactor_id=df_prog['reactor_id'],
                                          preculture=preculture,
                                          media=df_prog['media'],
                                          OD_setpoint=df_prog['OD_low'])
            else:
                prog = GrowDiluteProgram(user=df_prog['user'],
                                         campaign=df_prog['campaign'],
                                         short_name=df_prog['short_name'],
                                         description=df_prog['description'],
                                         reactor_id=df_prog['reactor_id'],
                                         preculture=preculture,
                                         media=df_prog['media'],
                                         OD_low=df_prog['OD_low'],
                                         OD_high=df_prog['OD_high'])

    def add_program(self, program):
        if program.reactor_id in self.programs:
            raise Exception('Reactor %i already used by a program !')
        self.programs[program.reactor_id] = program
        program._manager = self.manager

    def remove_program(self, rid):
        del self.programs[rid]

    def schedule_sampling(self, time_sampling):
        if self.fake_OT2:
            return 'CANNOT DO CYTOMETRY WITH FAKE OT2 !!!!!'
        if time_sampling > time() - 1:
            self.sampling_schedule.append(time_sampling)
        else:
            print('Cannot schedule the sampling: invalid sampling time (in the past)')
            
    def schedule_sec(self, time_sec):

        if self.automated_beads == False:
            print('experiment is not set up for automated beads measurements')
        
        else : 
            if self.fake_OT2:
                return 'CANNOT DO CYTOMETRY WITH FAKE OT2 !!!!!'
            if time_sec > time() - 1:
                self.sec_schedule.append(time_sec)
            else:
                print('Cannot schedule the sec measurement: invalid time (in the past)')

    def start(self):
        if self.status != 'running':
            print('Starting !')
            self.run_thread = SessionRun(self)
            self.run_thread.start()

    def pause(self):
        logging.info('T= {}| Pausing the session'.format(time()))
        print('Pausing session')
        if self.status == 'running':
            self.status = 'pausing'
            if self.run_thread is None:
                logging.error('T= {}| Trying to pause a session with no more run thread.'.format(time()))
            else:
                if not self.run_thread.is_alive():
                    logging.error('T= {}| Trying to pause a session with an inactive run thread ??'.format(time()))
            while self.status != 'paused':
                sleep(0.01)
        else:
            logging.info('T= {}| Trying to pause a session that is not running (status is {})'.format(time(),self.status))
            print('Not running ? status is {}.'.format(self.status))

    def stop(self):
        print('Stopping session')
        if self.status == 'running':
            self.status = 'stopping'
            while self.status != 'stopped':
                sleep(0.01)
        else:
            self.status = 'stopping'
            self.manager.shut_off_all_pumps_and_valves()
            self.status = 'stopped'
        # last data writing
        for program in self.programs.values():
            dfs = program.all_data_to_dfs()
            for data_type,df in dfs.items():
                if df is not None:
                    df.to_csv(program.output_path + '/' + data_type + '.csv', index=False)
                    # atlas
                    try:
                        df.to_csv(program.atlas_path + '/' + data_type + '.csv', index=False)
                    except BaseException as e:
                        logging.error('Something went wrong in atlas backup (error: {})'.format(e))

    def reset_all_sampling_state(self):
        
        self.ot2_plate_num = 1
        self.ot2_col = 12
        should_restart = False
        if self.status == 'running':
            should_restart = True
            self.pause()
        while input('WIPE WITH TISSUE THE SAMPLING LINES OUTPUT, AND RESTART THE FLASK APP OF THE ROBOT (INSTRUCTIONS AT THE BEGINNING OF THE NOTEBOOK). then wait for the robot movement and enter ok\n') != 'ok':
            pass
        self.manager.send_ot2_request('move_to/sampling_metal/12')
        while input('fine tune the plate position and enter ok\n') != 'ok':
            pass
        self.manager.send_ot2_request('move_to/sampling_metal/1')
        while input('fine tune the plate position and enter ok\n') != 'ok':
            pass
        self.manager.send_ot2_request('move_to/sampling_metal_2/12')
        while input('fine tune the plate position and enter ok\n') != 'ok':
            pass
        self.manager.send_ot2_request('move_to/sampling_metal_2/1')
        while input('fine tune the plate position and enter ok\n') != 'ok':
            pass
        self.manager.send_ot2_request('gotobin')
        if should_restart:
            self.start()
            
        self.sec_count = 1 # resetting the beads plate too 
            
        return 'Done sampling state reset... Means should be three clean sampling plates, three full reservoirs'

    def loop(self):
        try:
            ### beginning of the loop !
            loop_start_time = time()

            ## blink once
            try:
                self.manager.send_ot2_request('blink/1')
            except:
                pass

            ## OD measurements
            # first stop the bubbling because bubbles can affect OD
            bubbling_set_ids = ['B1','B2','B3']
            for bubbling_set_id in bubbling_set_ids:
                self.manager.set_valve_state(bubbling_set_id, True)
            if self.status != 'running':
                return
            # OD measurements per se
            reactor_set_ids = set([reactors[reactor_id].reactor_set_id for reactor_id in self.programs])
            OD_measuring_thread = ODMeasurement(self.manager, reactor_set_ids)
            OD_measuring_thread.start()
            while OD_measuring_thread.is_alive():
                if self.status != 'running':
                    sleep(0.1)
                    return
            ODs = OD_measuring_thread.ODs
            # provide the ODs to the programs
            for reactor_id in self.programs:
                self.programs[reactor_id].receive_OD_reading(ODs[reactor_id])
            # put back bubbling
            for bubbling_set_id in bubbling_set_ids:
                self.manager.set_valve_state(bubbling_set_id, False)

            ## drain via output
            # set output valve to the rest position, for which output pump takes from drain tube (should be useless because already off)
            for reactor_id,program in self.programs.items():
                self.manager.set_valve_state(reactors[reactor_id].out_valve_id, False)
            # position the robot to the bin so that we can collect the excess culture volume in the bioharzard tank
            self.manager.send_ot2_request('gotobin')
            # open the output pumps for the duration
            drain_threads = []
            for reactor_id,program in self.programs.items():
                if program.drain_out_pump_duration_s > 0:
                    drain_threads.append(self.manager.open_pump_for_duration(reactors[reactor_id].pump_out_slot_id, program.drain_out_pump_duration_s))
            if not self.virtual_mode:
                for drain_thread in drain_threads:
                    drain_thread.join()

            ## blink twice
            try:
                self.manager.send_ot2_request('blink/2')
            except:
                pass

            ## media addition
            dilution_threads = []
            for reactor_id,program in self.programs.items():
                dilution_duration = program.compute_dilution_duration()
                if dilution_duration:
                    program.drain_out_pump_duration_s = 4 * dilution_duration
                    dilution_threads.append(
                        self.manager.open_pump_for_duration(reactors[reactor_id].pump_in_slot_id, dilution_duration))
                else:
                    program.drain_out_pump_duration_s = 0.
            for dilution_thread in dilution_threads:
                dilution_thread.join()

            ## blink thrice
            try:
                self.manager.send_ot2_request('blink/3')
            except:
                pass

            ## are we waiting for data ? if arrives, we should wash
            
            # and self.waiting_for_guava_data_sec == False and self.should_wash_row2 == False
            
            if self.waiting_for_guava_data :
                # check if the guava is finished
                if self.manager.send_guava_request('status') == 'finished':
                    # get the raw fcs
                    raw_fcs = self.manager.send_guava_request('retrieve_data', is_file=True)
                    # parsing of fcs data
                    with open('raw.fcs', 'wb') as fcs_writing:
                        fcs_writing.write(raw_fcs)
                    fcs3 = guava2data.GuavaFCS3('raw.fcs')
                    os.remove('raw.fcs')
                    # update loop status
                    self.waiting_for_guava_data = False
                    self.should_wash = True
                    logging.info('T= {}| Got the fcs3 file from the guava'.format(time()))
                    for reactor_id,program in self.programs_with_cytometry.items():
                        if program.samplings['guava_fcs_file']:
                            program.samplings['guava_fcs_file'][-1] = 'fetched'
                            guava_well = reactors[reactor_id].guava_row + reactors[reactor_id].guava_col
                            if guava_well not in fcs3.samples:
                                logging.info('T= {}| cannot find data for well {} ?!'.format(time(),guava_well))
                                continue
                            logging.info('T= {}| loading data for well {}'.format(time(),guava_well))
                            sample = fcs3.get_sample(guava_well)
                            sample_df = sample.to_df(min_n_return_none=2)
                            logging.info('T= {}| finished loading data for well {}'.format(time(),guava_well))
                            # only take sample if expected number of events
                            if sample_df is not None and len(sample_df) == self.guava_num_events:
                                logging.info('T= {}| data for well {} has good number of events'.format(time(),guava_well))
                                # add the sampling_time_s as a columns
                                sample_df['sampling_time_s'] = program.samplings['time_s'][-1]
                                if program.cells is None:
                                    program.cells = sample_df
                                else:
                                    program.cells = pd.concat([program.cells, sample_df], ignore_index=True)
                                program.cells.to_csv(f'{program.output_path}/cells.csv', index=False)
                                if False:
                                    program.cells.to_csv(f'{program.atlas_path}/cells.csv', index=False)
                            else:
                                if sample_df is not None:
                                    logging.info('T= {}| not enough events ! only {}'.format(time(),len(sample_df)))
                                else:
                                    logging.info('T= {}| less than 2 events !!!!!!!'.format(time()))

            
            ## should we wash the guava plate ?
            if self.should_wash:
                self.manager.send_guava_request('toggle_tray')
                # do the wash
                for i in range(3):
                    self.manager.send_ot2_request(f'wash_from_trough/{self.ot2_plate_num}/{self.ot2_col}')
                # update plate num and col
                self.ot2_col -= 1
                if self.ot2_col < 1:
                    self.ot2_plate_num += 1
                    self.ot2_col = 12
                self.manager.send_guava_request('toggle_tray')
                self.should_wash = False
                  

            ## should we sample to the guava and start acquire ?
            if not self.waiting_for_guava_data and not self.waiting_for_guava_data_sec and not self.should_wash_row2 :
                # check if we passed the time of the next sampling
                if self.sampling_schedule:
                    
                    next_sampling_time = sorted(self.sampling_schedule)[0]
                    logging.info('T= {}| next_sampling_time'.format(next_sampling_time))
                    
                    try:
                        next_sec_time = sorted(self.sec_schedule)[0]
                        entering = next_sampling_time < next_sec_time
                        
                    except:
                        next_sec_time = None
                        entering = True
                        
                    logging.info('T= {}| next_sec_time'.format(next_sec_time))
                    
                    if entering : 
                    
                        if next_sampling_time < time():
                            logging.info('T= {}| We passed time of a scheduled sampling'.format(time()))
                            # check that we can do the sampling
                            assert(self.ot2_plate_num in [1,2])
                            assert(self.ot2_col in [1,2,3,4,5,6,7,8,9,10,11,12])
                            # decide programs that we can sample based on volume estimate
                            programs_to_sample = {}
                            for reactor_id, program in self.programs_with_cytometry.items():
                                vol_estim = program.volume_estimates
                                if not self.low_volume_no_sampling_safety or vol_estim.empty or vol_estim['volume_estimation_mL'].iloc[-1] > 12:
                                    programs_to_sample[reactor_id] = program
                            # start the sampling !
                            real_sampling_time = time()
                            self.sampling_schedule.remove(next_sampling_time)
                            self.samplings.append(real_sampling_time)
                            # record the sampling into each program so that can be output
                            for reactor_id, program in programs_to_sample.items():
                                program.samplings['time_s'].append(real_sampling_time)
                                program.samplings['guava_well'].append(reactors[reactor_id].guava_row + reactors[reactor_id].guava_col)
                                program.samplings['guava_fcs_file'].append('not_fetched_yet')
                                program.samplings['sampling_plate_and_col'].append(f'plate-{self.ot2_plate_num}_col-{self.ot2_col}')
                            # move the sampling output above the thrash
                            self.manager.send_ot2_request('gotobin')
                            # set the out valve to sampling
                            for reactor_id,program in programs_to_sample.items():
                                self.manager.set_valve_state(reactors[reactor_id].out_valve_id, True)
                            # gather the out slots and dead volumes
                            pump_out_slot_ids = [reactors[reactor_id].pump_out_slot_id for reactor_id in programs_to_sample]
                            dead_volumes = [program.dead_volume_sampling_line_mL for program in programs_to_sample.values()]
                            # dead volume first
                            pump_threads = []
                            for pump_out_slot_id,dead_volume in zip(pump_out_slot_ids, dead_volumes):
                                pump_threads.append(
                                    self.manager.open_pump_for_volume(pump_out_slot_id, dead_volume))
                            if not self.virtual_mode:
                                for pump_thread in pump_threads:
                                    pump_thread.join()
                            # do volume renewal if activated
                            pump_in_slot_ids = [reactors[reactor_id].pump_in_slot_id for reactor_id,program in programs_to_sample.items() if program.renew_sampled_volume]
                            dead_volumes = [program.dead_volume_sampling_line_mL for program in programs_to_sample.values() if program.renew_sampled_volume]
                            pump_threads = []
                            for pump_in_slot_id,dead_volume in zip(pump_in_slot_ids, dead_volumes):
                                pump_threads.append(
                                    self.manager.open_pump_for_volume(pump_in_slot_id, dead_volume))
                            # declare the dilutions to the program
                            for reactor_id,program in programs_to_sample.items():
                                if program.renew_sampled_volume:
                                    program.dilutions['time_s'].append(time())
                                    program.dilutions['duration_s'].append(program.dead_volume_sampling_line_mL / self.manager.input_pump_flow_rate_mL_min(reactor_id) * 60.)
                                    program.dilutions['est_flow_rate_uL_per_s'].append(self.manager.input_pump_flow_rate_mL_min(reactor_id)/60.*1000.)
                            if not self.virtual_mode:
                                for pump_thread in pump_threads:
                                    pump_thread.join()
                            # shake the ot2 arm to remove ready to fall drops
                            self.manager.send_ot2_request('shakeit')
                            # move into sampling position (first cytoplate for path optim reason)
                            self.manager.send_ot2_request(f'move_to/cytoplate/2')
                            plate_labware_name = {1:'sampling_metal', 2:'sampling_metal_2'}[self.ot2_plate_num]
                            self.manager.send_ot2_request(f'move_to/{plate_labware_name}/{self.ot2_col}')
                            # sampling !
                            pump_threads = []
                            for pump_out_slot_id in pump_out_slot_ids:
                                pump_threads.append(
                                    self.manager.open_pump_for_duration(pump_out_slot_id, 0.75))
                            if not self.virtual_mode:
                                for pump_thread in pump_threads:
                                    pump_thread.join()
                            # prepare the guava (will make the worklist, and open the tray)
                            guava_wells = [reactors[reactor_id].guava_row + reactors[reactor_id].guava_col for reactor_id in programs_to_sample]
                            guava_wells_str = '_'.join(guava_wells)
                            self.manager.send_guava_request(f'prepare/{guava_wells_str}/{self.guava_num_events}')
                            # move to cytoplate plate then to bin to minimize cross-cont while moving
                            self.manager.send_ot2_request(f'move_to/cytoplate/2')
                            self.manager.send_ot2_request('gotobin')
                            # fill guava plate
                            self.manager.send_ot2_request(f'dilute/10/{self.ot2_plate_num}/{self.ot2_col}')
                            if self.additional_cytoplate_dilution:
                                raise Exception('additional cytoplate dil not supported anymore')
                            # start guava acquisition (careful !!!!!!!! on the background, we know its finished only when fcs data appears on atlas)
                            self.manager.send_guava_request('acquire')
                            # store that the sampling has been done, so one should wait for guava data
                            self.waiting_for_guava_data = True

            ## output data
            for program in self.programs.values():
                dfs = program.all_data_to_dfs()
                for data_type,df in dfs.items():
                    if df is not None:
                        df.to_csv(program.output_path + '/' + data_type + '.csv', index=False)
                        # also write data to ATLAS
                        try:
                            df.to_csv(program.atlas_path + '/' + data_type + '.csv', index=False)
                        except BaseException as e:
                            logging.error('Something went wrong in atlas backup (error: {})'.format(e))

                            
                        
            # --------------------------------------------------------------------------------------------------------------
            # NEW STUFF FOR BEADS AUTOMATION 
            # --------------------------------------------------------------------------------------------------------------
            
            # in the following paragraphs, I just copied and pasted the paragrpahe above and slightly changed it to 
            # apply it for sec measurements 
           
            ## are we waiting for data ? if arrives, we should wash
            if self.waiting_for_guava_data_sec:
                # check if the guava is finished
                if self.manager.send_guava_request('status') == 'finished':
                    # get the raw fcs
                    raw_fcs = self.manager.send_guava_request('retrieve_data', is_file=True)
                    # parsing of fcs data
                    with open('raw.fcs', 'wb') as fcs_writing:
                        fcs_writing.write(raw_fcs)
                    fcs3 = guava2data.GuavaFCS3('raw.fcs')
                    os.remove('raw.fcs')
                    # update loop status
                    self.waiting_for_guava_data_sec = False
                    self.should_wash_row2 = True
                    logging.info('T= {}| Got the fcs3 file from the guava'.format(time()))
                    
                    for reactor_id,program in self.programs_with_cytometry.items():
                        if program.samplings['guava_fcs_file']:
                            program.samplings['guava_fcs_file'][-1] = 'fetched'
                            #guava_well = reactors[reactor_id].guava_row + reactors[reactor_id].guava_col
                            #guava_well = reactors[reactor_id].guava_row + '11'
                            guava_well = reactors[reactor_id].guava_row + '12'
                            
                            if guava_well not in fcs3.samples:
                                logging.info('T= {}| cannot find data for well {} ?!'.format(time(),guava_well))
                                continue
                            logging.info('T= {}| loading data for well {}'.format(time(),guava_well))
                            sample_sec = fcs3.get_sample(guava_well)
                            sample_df_sec = sample_sec.to_df(min_n_return_none=2)
                            logging.info('T= {}| finished loading data for well {}'.format(time(),guava_well))
                            # only take sample if expected number of events # nope, we won't do that for beads
                            if sample_df_sec is not None :
                                #and len(sample_df_sec) == self.guava_num_events:   
                                #logging.info('T= {}| data for well {} has good number of events'.format(time(),guava_well))

                                # add the sampling_time_s as a columns
                                sample_df_sec['sampling_time_s'] = program.samplings['time_s'][-1]
                                if program.beads is None:
                                    program.beads = sample_df_sec
                                else:
                                    program.beads = pd.concat([program.beads, sample_df_sec], ignore_index=True)
                                program.beads.to_csv(f'{program.output_path}/beads.csv', index=False)
                                if False:
                                    program.beads.to_csv(f'{program.atlas_path}/beads.csv', index=False)
                            else:
                                if len(sample_df_sec) != self.guava_num_events: 
                                    if sample_df_sec is not None:
                                        logging.info('T= {}| not enough events ! only {}'.format(time(),len(sample_df_sec)))
                                    else:
                                        logging.info('T= {}| less than 2 events !!!!!!!'.format(time()))
            
            ## should we wash the guava plate ?
            if self.should_wash_row2:
                self.manager.send_guava_request('toggle_tray')
                # do the wash
                for i in range(3):
                    count = self.sec_count + 6
                    self.manager.send_ot2_request(f'wash_row_beads/{count}')
                    # self.manager.send_ot2_request(f'wash_row_2/{count}')
                    # self.manager.send_ot2_request(f'wash_row_2/{ot2.col}')
                    
                # update plate num and col --> not anymore bc we have a secretion sampling plate now
                '''
                self.ot2_col -= 1
                if self.ot2_col < 1:
                    self.ot2_plate_num += 1
                    self.ot2_col = 12
                '''
                self.sec_count += 1 
                self.manager.send_guava_request('toggle_tray')
                self.should_wash_row2 = False
                
            ## should we sample to the guava and start acquire ?
            if not self.waiting_for_guava_data_sec and not self.waiting_for_guava_data and not self.should_wash:
                # check if we passed the time of the next sampling
                if self.sec_schedule:
                    next_sec_time = sorted(self.sec_schedule)[0]
                    if next_sec_time < time():
                        logging.info('T= {}| We passed time of a scheduled sec measure'.format(time()))

                        # decide programs that we can sample based on volume estimate
                        programs_to_sample = {}
                        for reactor_id, program in self.programs_with_cytometry.items():
                            vol_estim = program.volume_estimates
                            if not self.low_volume_no_sampling_safety or vol_estim.empty or vol_estim['volume_estimation_mL'].iloc[-1] > 12:
                                programs_to_sample[reactor_id] = program
                        # start the sampling !
                        real_sec_time = time()
                        self.sec_schedule.remove(next_sec_time)
                        self.secs.append(real_sec_time)
                        # record the sampling into each program so that can be output
                        for reactor_id, program in programs_to_sample.items():
                            program.samplings['time_s'].append(real_sec_time)
                            #program.samplings['guava_well'].append(reactors[reactor_id].guava_row + '11')     #reactors[reactor_id].guava_col
                            program.samplings['guava_well'].append(reactors[reactor_id].guava_row + '12')     #reactors[reactor_id].guava_col
                            
                            program.samplings['guava_fcs_file'].append('not_fetched_yet')
                            #program.samplings['sampling_plate_and_col'].append(f'plate-{self.ot2_plate_num}_col-{self.ot2_col}')
                            #sec_count = len(self.secs) --> deprecated now that we have self.sec_count
                            program.samplings['sampling_plate_and_col'].append(f'plate-3_col-{self.sec_count}')
                            
                        # move the sampling output above the thrash
                        self.manager.send_ot2_request('gotobin')
                        # set the out valve to sampling
                        for reactor_id,program in programs_to_sample.items():
                            self.manager.set_valve_state(reactors[reactor_id].out_valve_id, True)
                        # gather the out slots and dead volumes
                        pump_out_slot_ids = [reactors[reactor_id].pump_out_slot_id for reactor_id in programs_to_sample]
                        dead_volumes = [program.dead_volume_sampling_line_mL for program in programs_to_sample.values()]
                        # dead volume first
                        pump_threads = []
                        for pump_out_slot_id,dead_volume in zip(pump_out_slot_ids, dead_volumes):
                            pump_threads.append(
                                self.manager.open_pump_for_volume(pump_out_slot_id, dead_volume))
                        if not self.virtual_mode:
                            for pump_thread in pump_threads:
                                pump_thread.join()
                                
                        # do volume renewal if activated
                        pump_in_slot_ids = [reactors[reactor_id].pump_in_slot_id for reactor_id,program in programs_to_sample.items() if program.renew_sampled_volume]
                        dead_volumes = [program.dead_volume_sampling_line_mL for program in programs_to_sample.values() if program.renew_sampled_volume]
                        pump_threads = []
                        for pump_in_slot_id,dead_volume in zip(pump_in_slot_ids, dead_volumes):
                            pump_threads.append(
                                self.manager.open_pump_for_volume(pump_in_slot_id, dead_volume))
                        # declare the dilutions to the program
                        for reactor_id,program in programs_to_sample.items():
                            if program.renew_sampled_volume:
                                program.dilutions['time_s'].append(time())
                                program.dilutions['duration_s'].append(program.dead_volume_sampling_line_mL / self.manager.input_pump_flow_rate_mL_min(reactor_id) * 60.)
                                program.dilutions['est_flow_rate_uL_per_s'].append(self.manager.input_pump_flow_rate_mL_min(reactor_id)/60.*1000.)
                        if not self.virtual_mode:
                            for pump_thread in pump_threads:
                                pump_thread.join()
                        # shake the ot2 arm to remove ready to fall drops
                        self.manager.send_ot2_request('shakeit')
                        # move into sampling position (first cytoplate for path optim reason)
                        self.manager.send_ot2_request(f'move_to/cytoplate/1')
                        #plate_labware_name = {1:'sampling_metal', 2:'sampling_metal_2'}[self.ot2_plate_num]
                        #self.manager.send_ot2_request(f'move_to/{plate_labware_name}/{self.ot2_col}')
                        
                        self.manager.send_ot2_request(f'move_to/sampling_metal_3/{self.sec_count}')
                        # sampling !
                        pump_threads = []
                        for pump_out_slot_id in pump_out_slot_ids:
                            pump_threads.append(
                                self.manager.open_pump_for_duration(pump_out_slot_id, 0.75))
                        if not self.virtual_mode:
                            for pump_thread in pump_threads:
                                pump_thread.join()

                        ################# MY FUNCTION OF SEC MEASUREMENT #######################

                        # this whole block hereabove is replace by this single line : 
                        
                        self.manager.send_ot2_request(f'wash_beads/100/{self.sec_count}/{self.sec_count+6}')
                        
                        # launch a new aquisition 
                        
                        #self.manager.send_guava_request('prepare/A11_B11_C11_D11_E11_F11_G11_H11/5000') 
                        # 11 because 2nd row of the cytoplate
                        self.manager.send_guava_request('prepare/A12_B12_C12_D12_E12_F12_G12_H12/5000') 
                        # it become 12 because Sara swapped the two rows of the cytoplate
                         
                        # load the beads from the mag_plate to the cytoplate
                        #self.manager.send_ot2_request(f'transfer/200/mag_plate/{self.sec_count}/cytoplate/2/')
                        # this line aboce is replaced by the following one : 
                        self.manager.send_ot2_request(f'load_beads/{self.sec_count}')
                        # this will click on the last OK on guava computer to launch aquisition
                        # it will close the tray 
                        self.manager.send_guava_request('acquire')
                        # store that the sampling has been done, so one should wait for guava data
                        self.waiting_for_guava_data_sec = True
                        
                        ############### END OF MY FUNCTION ############### 

            ## output data
            for program in self.programs.values():
                dfs = program.all_data_to_dfs()
                for data_type,df in dfs.items():
                    if df is not None:
                        df.to_csv(program.output_path + '/' + data_type + '.csv', index=False)
                        # also write data to ATLAS
                        try:
                            df.to_csv(program.atlas_path + '/' + data_type + '.csv', index=False)
                        except BaseException as e:
                            logging.error('Something went wrong in atlas backup (error: {})'.format(e))
                            
            # -------------------------------------------------------------------------------------------------------
            # END OF THE NEW STUFF
            # -------------------------------------------------------------------------------------------------------
            
            
            ## update LED change data
            led_histories = self.manager.get_all_leds_history()
            for reactor_id,program in self.programs.items():
                program.update_LED_data(led_histories[reactor_id])

            ## check and apply events
            logging.info('T= {}| Starting to check events'.format(time()))
            for rid,program in self.programs.items():
                logging.info('T= {}| Starting to check events of reactor id {}'.format(time(), program.reactor_id))
                for i_event,event in enumerate(program.events):
                    try:
                        event.check_and_apply(program)
                    except BaseException as e:
                        message = f'Something went wrong (error: {e}) when checking event #{i_event} of reactor {rid}.'
                        logging.error(message)
                        self.manager.send_discord(message)

            ## wait until next loop
            self.loop_counter += 1
            while time() - loop_start_time < self.loop_duration_s:
                if self.status != 'running':
                    return
                sleep(0.1)

        except BaseException as e:
            message = f'Something went wrong (error: {e}). Main loop continues, BE CAREFUL / CHECK'
            logging.error(message)
            self.manager.send_discord(message)
            while time() - loop_start_time < self.loop_duration_s:
                sleep(0.1)

    ## useful functions to use outside of main loop

    def prime_input_pumps(self,open_duration_s=6):
        try:
            reactor_ids = self.programs.keys()
            logging.info('T= %f| Started an input pumps priming sequence' % time())
            while input('Priming of pumps with liquid. Make sure pump output is setup as desired. Enter y to flow for %f seconds, otherwise ok\n'%open_duration_s) == 'y':
                pump_threads = []
                for reactor_id in reactor_ids:
                    pump_threads.append(
                        self.manager.open_pump_for_duration(reactors[reactor_id].pump_in_slot_id, open_duration_s))
                for pump_thread in pump_threads:
                    pump_thread.join()
        except BaseException as e:
            logging.error('Something went wrong, shutting off all coils. (error: %s)' % str(e))
            self.manager.shut_off_all_pumps_and_valves()

    def pinch_drain_valves(self, reactor_ids=None):
        try:
            if reactor_ids is None:
                reactor_ids = self.programs.keys()
            logging.info('T= %f| Pinching front valves' % time())
            for reactor_id in reactor_ids:
                    self.manager.set_valve_state(reactors[reactor_id].out_valve_id, True)
        except BaseException as e:
            logging.error('Something went wrong, shutting off all coils. (error: %s)' % str(e))
            self.manager.shut_off_all_pumps_and_valves()

    def unpinch_drain_valves(self, reactor_ids=None):
        try:
            if reactor_ids is None:
                reactor_ids = self.programs.keys()
            logging.info('T= %f| Pinching front valves' % time())
            for reactor_id in reactor_ids:
                    self.manager.set_valve_state(reactors[reactor_id].out_valve_id, False)
        except BaseException as e:
            logging.error('Something went wrong, shutting off all coils. (error: %s)' % str(e))
            self.manager.shut_off_all_pumps_and_valves()

    def add_media(self,volume_mL, cleaning=False):
        try:
            if cleaning:
                reactor_ids = self.reactor_ids_to_clean
            else:
                reactor_ids = self.programs.keys()
            logging.info('T= %f| Started an input pumps sequence' % time())
            pump_threads = []
            for reactor_id in reactor_ids:
                pump_threads.append(
                    self.manager.open_pump_for_volume(reactors[reactor_id].pump_in_slot_id, volume_mL))
            for pump_thread in pump_threads:
                pump_thread.join()
        except BaseException as e:
            logging.error('Something went wrong, shutting off all coils. (error: %s)' % str(e))
            self.manager.shut_off_all_pumps_and_valves()

    def remove_volume(self, volume_mL, cleaning=False, pinch_drain_valves=True):
        try:
            self.manager.send_ot2_request('gotobin')
            if cleaning:
                reactor_ids = self.reactor_ids_to_clean
            else:
                reactor_ids = self.programs.keys()
            if pinch_drain_valves:
                self.pinch_drain_valves(reactor_ids)
            pump_threads = []
            for reactor_id in reactor_ids:
                pump_threads.append(
                    self.manager.open_pump_for_volume(reactors[reactor_id].pump_out_slot_id, volume_mL))
            for pump_thread in pump_threads:
                pump_thread.join()
            self.unpinch_drain_valves(reactor_ids)
        except BaseException as e:
            logging.error('Something went wrong, shutting off all coils. (error: %s)' % str(e))
            self.manager.shut_off_all_pumps_and_valves()

    # for cleaning
    def register_reactors_for_cleaning(self, reactor_ids):
        for reactor_id in reactor_ids:
            if reactor_id in self.programs:
                del self.programs[reactor_id]
        self.reactor_ids_to_clean = reactor_ids

    def start_input_flow(self, reactor_ids=None):
        if reactor_ids is None:
            reactor_ids = self.programs.keys()
        for reactor in [reactors[id] for id in reactor_ids]:
            self.manager.set_pump_state(reactor.pump_in_slot_id, True)

    def stop_input_flow(self, reactor_ids=None):
        if reactor_ids is None:
            reactor_ids = self.programs.keys()
        for reactor in [reactors[id] for id in reactor_ids]:
            self.manager.set_pump_state(reactor.pump_in_slot_id, False)

    def start_output_flow(self, reactor_ids=None):
        self.manager.send_ot2_request('gotobin')
        if reactor_ids is None:
            reactor_ids = self.programs.keys()
        for reactor in [reactors[id] for id in reactor_ids]:
            self.manager.set_pump_state(reactor.pump_out_slot_id, True)

    def stop_output_flow(self, reactor_ids=None):
        if reactor_ids is None:
            reactor_ids = self.programs.keys()
        for reactor in [reactors[id] for id in reactor_ids]:
            self.manager.set_pump_state(reactor.pump_out_slot_id, False)

    def start_output_pump_calibration(self):
        duration_seconds = {}
        for rid in self.reactor_ids_to_clean:
            self.manager.set_pump_state(f'H{rid}', True)
            tstart = time()
            input()
            tend = time()
            self.manager.set_pump_state(f'H{rid}', False)
            duration_seconds[rid] = tend - tstart
            sleep(3)
        pump_flow_rates = {rid:9.5/T*60 for rid,T in duration_seconds.items()}
        for rid,flow_rate in pump_flow_rates.items():
            pump_id = self.manager.output_pumps[rid]
            old_flow_rate = self.manager.pump_calib_pars.loc[pump_id, 'flow_rate_mL_min']
            print(f'For pump {pump_id} (installed as output for reactor {rid}), new flow rate: {flow_rate} mL/min (was {old_flow_rate})')
            logging.info(f'For pump {pump_id} (installed as output for reactor {rid}), new flow rate: {flow_rate} mL/min (was {old_flow_rate})')
            self.manager.pump_calib_pars.loc[pump_id, 'flow_rate_mL_min'] = flow_rate
            self.manager.pump_calib_pars.loc[pump_id, 'date'] = date.today()
        self.manager.pump_calib_pars.to_csv('cytoreactors/calibration/pump-calibration-parameters.csv')

    def start_input_pump_calibration(self):
        duration_seconds = {}
        for rid in self.reactor_ids_to_clean:
            self.manager.set_pump_state(f'L{rid}', True)
            tstart = time()
            input()
            tend = time()
            self.manager.set_pump_state(f'L{rid}', False)
            duration_seconds[rid] = tend - tstart
            sleep(3)
        pump_flow_rates = {rid:9.5/T*60 for rid,T in duration_seconds.items()}
        for rid,flow_rate in pump_flow_rates.items():
            pump_id = self.manager.input_pumps[rid]
            old_flow_rate = self.manager.pump_calib_pars.loc[pump_id, 'flow_rate_mL_min']
            print(f'For pump {pump_id} (installed as input for reactor {rid}), new flow rate: {flow_rate} mL/min (was {old_flow_rate})')
            logging.info(f'For pump {pump_id} (installed as input for reactor {rid}), new flow rate: {flow_rate} mL/min (was {old_flow_rate})')
            self.manager.pump_calib_pars.loc[pump_id, 'flow_rate_mL_min'] = flow_rate
            self.manager.pump_calib_pars.loc[pump_id, 'date'] = date.today()
        self.manager.pump_calib_pars.to_csv('cytoreactors/calibration/pump-calibration-parameters.csv')



    ## plotting utilities

    def plot_reactor_group(self, reactor_ids=None, xlims=None, show_fl=False, ch_fl='GRN-B-HLin'):
        if reactor_ids is None:
            reactor_ids = list(self.programs.keys())
        if show_fl:
            ax_OD, ax_gr, ax_LEDs, ax_fl = self.programs[reactor_ids[0]].plot(show_fl=show_fl, ch_fl=ch_fl)
        else:
            ax_OD, ax_gr, ax_LEDs = self.programs[reactor_ids[0]].plot(show_fl=show_fl, ch_fl=ch_fl)
        for rid in reactor_ids[1:]:
            if show_fl:
                self.programs[rid].plot(axs=(ax_OD, ax_gr, ax_LEDs, ax_fl), show_fl=show_fl, ch_fl=ch_fl)
            else:
                self.programs[rid].plot(axs=(ax_OD, ax_gr, ax_LEDs), show_fl=show_fl, ch_fl=ch_fl)
        if show_fl:
            for ax in [ax_OD,ax_gr,ax_LEDs,ax_fl]:
                ax.grid()
                if xlims:
                    ax.set_xlim(xlims)
            return ax_OD, ax_gr, ax_LEDs, ax_fl
        for ax in [ax_OD, ax_gr, ax_LEDs]:
            ax.grid()
            if xlims:
                ax.set_xlim(xlims)
        return ax_OD, ax_gr, ax_LEDs


# thread that terminates when session is not running
class SessionRun(Thread):
    def __init__(self, session):
        super().__init__()
        self.session = session
    def run(self):
        if self.session.status != 'running':
            self.session.status = 'running'
            while self.session.status == 'running':
                self.session.loop()
        if self.session.status == 'pausing':
            self.session.manager.shut_off_all_pumps_and_valves()
            self.session.status = 'paused'
            while self.session.status == 'paused':
                sleep(0.1)
        elif self.session.status == 'stopping':
            self.session.manager.shut_off_all_pumps_and_valves()
            self.session.status = 'stopped'
        else:
            logging.error('T= {}| Unknown session status {}'.format(time(),self.session.status))
            print('unknown session status {}'.format(self.session.status))

# thread for OD measurements
class ODMeasurement(Thread):
    def __init__(self, manager, reactor_set_ids):
        super().__init__()
        self.manager = manager
        self.reactor_set_ids = reactor_set_ids
        self.ODs = None
    def run(self):
        self.ODs = self.manager.get_turbidity_readings(self.reactor_set_ids)
