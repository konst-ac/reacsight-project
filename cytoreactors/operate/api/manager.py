## imports
from cytoreactors.operate.api.device import Device
from cytoreactors import __path__ as package_path_list
package_path = package_path_list[0]
# print('package path = %s' % package_path)
import queue
import threading
import logging
from time import time, sleep
from datetime import date
import os
import pandas as pd
import numpy as np
import git
import requests



class Manager:

    def __init__(self, use_wago_only=False, fake_OT2=False, virtual_mode=False):
        self.use_wago_only = use_wago_only
        self.fake_OT2 = fake_OT2
        self.virtual_mode = virtual_mode
        self.start_log()
        if not self.virtual_mode:
            self.device = Device(use_wago_only=self.use_wago_only, fake_OT2=self.fake_OT2)
            self.od_calib_pars = pd.read_csv(package_path + '/calibration/turbidity-calibration-parameters.csv', index_col=0)
            self.pump_calib_pars = pd.read_csv(package_path + '/calibration/pump-calibration-parameters.csv', index_col=0)
            self.input_pumps = {rid:None for rid in range(1,17)}
            self.output_pumps = {rid:None for rid in range(1,17)}
            self.discord_webhook = 'https://discordapp.com/api/webhooks/740523581552722012/3I3bHoJxnndfGpEOmpZ7CtqpA-JSevL_MiGTbMWNeNhuzPpDHAoxSCeYntVbuI7EfyhU'

    def start_log(self):
        session_log_filepath = package_path + '/logs/operation_%s_%i.log' % (date.today(),time())
        print('Logging filepath = %s' % session_log_filepath)
        logging.basicConfig(filename=session_log_filepath, filemode='w', level=logging.INFO)
        ## log the git commit id
        repo = git.Repo(search_parent_directories=True)
        sha = repo.head.object.hexsha
        self.log_item('GLOBAL', f'opto-cyto-reactors cod git id ={sha}')

    def send_discord(self, message):
        try:
            requests.post(self.discord_webhook, data={'content':message})
        except:
            pass

    def is_active(self):
        if self.virtual_mode:
            return True
        return self.device.is_connected

    def stop(self):
        self.log_item('GLOBAL', 'STOP session')
        self.shut_off_all_pumps_and_valves()
        self.log_item('GLOBAL', 'Finished STOP session')
        if not self.virtual_mode:
            self.device.disconnect()

    def log_item(self, domain, message, is_error=False, is_warning=False):
        t = time()
        log_line = f'T={t} | domain={domain} | msg={message}'
        if self.virtual_mode:
            log_line += ' | virtual'
        if is_error:
            logging.error(log_line)
        elif is_warning:
            logging.warning(log_line)
        else:
            logging.info(log_line)

    def add_new_pump(self, name, flow_rate_mL_min=12):
        new_pump = self.pump_calib_pars.xs(self.pump_calib_pars.index[-1]).copy()
        new_pump.name = name
        new_pump['date'] = date.today()
        new_pump['flow_rate_mL_min'] = flow_rate_mL_min
        self.pump_calib_pars = self.pump_calib_pars.append(new_pump)
        self.pump_calib_pars.to_csv('cytoreactors/calibration/pump-calibration-parameters.csv')

    ## function to set pump state and verifying it worked
    def set_pump_state(self, pump_slot_id, pump_state):
        pump_state_str = {0:'OFF', 1:'ON'}[pump_state]
        if self.virtual_mode:
            self.log_item('PUMP', f'PUMP {pump_slot_id} {pump_state_str}')
            return
        if not self.is_active():
            raise Exception('Manager is not active ?')
        logging.info('T= %f | asked for command Pump %s %s' % (time(),pump_slot_id,pump_state_str))
        # check if state already as asked and warn if it is the case
        previous_pump_state = self.device.read_pump_state(pump_slot_id)
        while previous_pump_state is None:
            logging.warning('reading Pump %s state not successful, trying again' % pump_slot_id)
            previous_pump_state = self.device.read_pump_state(pump_slot_id)
        if previous_pump_state == pump_state:
            logging.warning('useless (state already as asked) command asked Pump %s %s, so not doing it' % (pump_slot_id,pump_state_str))
            return
        # send command, check success, if not try again until success
        self.device.send_pump_command(pump_slot_id, pump_state)
        sleep(0.01)
        while self.device.read_pump_state(pump_slot_id) != pump_state:
            logging.warning('command Pump %s %s not successful, trying again' % (pump_slot_id,  {0:'OFF', 1:'ON'}[pump_state]))
            self.device.send_pump_command(pump_slot_id, pump_state)
            sleep(0.01)
        logging.info('T= %f | finished for command Pump %s %s' % (time(), pump_slot_id,  {0:'OFF', 1:'ON'}[pump_state]))

    ## function to open a pump for a fixed duration (using threading.Timer)
    def open_pump_for_duration(self, pump_slot_id, duration_s, blocking=False, wait_after=0.):
        if self.virtual_mode:
            self.log_item('PUMP', f'PUMP {pump_slot_id} OPEN FOR {duration_s}')
            return
        if not self.is_active():
            raise Exception('Manager is not active ?')
        logging.info('T= %f | asked for opening Pump %s for duration %f seconds' % (time(),pump_slot_id, duration_s))
        if duration_s < 0.1:
            logging.warning('Asked for opening Pump %s for too short duration (%f), not doing it' % (pump_slot_id, duration_s))
        self.set_pump_state(pump_slot_id, True)
        close_thread = threading.Timer(duration_s, self.set_pump_state, (pump_slot_id, False))
        close_thread.start()
        if blocking:
            close_thread.join()
            sleep(wait_after)
        return close_thread

    def input_pump_flow_rate_mL_min(self, rid):
        return self.pump_calib_pars.loc[self.input_pumps[rid], 'flow_rate_mL_min']

    def output_pump_flow_rate_mL_min(self, rid):
        return self.pump_calib_pars.loc[self.output_pumps[rid], 'flow_rate_mL_min']

    def open_pump_for_volume(self, pump_slot_id, volume_mL, blocking=False, wait_after=0.):
        rid = int(pump_slot_id[1:])
        flow_rate_mL_min = {'L':self.input_pump_flow_rate_mL_min(rid),
                            'H':self.output_pump_flow_rate_mL_min(rid)}[pump_slot_id[0]]
        duration_s = volume_mL / flow_rate_mL_min * 60.
        return self.open_pump_for_duration(pump_slot_id, duration_s, blocking, wait_after)

    ## function to read the state of a pump
    def get_pump_state(self, pump_slot_id):
        if not self.is_active():
            raise Exception('Manager is not active ?')
        logging.info('T= %f | asked for reading state of Pump slot %s' % (time(),pump_slot_id))
        pump_state = self.device.read_pump_state(pump_slot_id)
        while pump_state is None:
            logging.warning('reading Pump slot %s state not successful, trying again' % pump_slot_id)
            pump_state = self.device.read_pump_state(pump_slot_id)
        logging.info('T= %f | state of Pump slot %s is %s' % (time(),pump_slot_id,pump_state))
        return pump_state

    ## function to set valve state and verifying it worked
    def set_valve_state(self, valve_id, valve_state):
        valve_state_str = {0:'OFF', 1:'ON'}[valve_state]
        if self.virtual_mode:
            self.log_item('VALVE', f'VALVE {valve_id} {valve_state}')
            return
        if not self.is_active():
            raise Exception('Manager is not active ?')
        logging.info('T= %f | asked for command Valve %s %s' % (time(),valve_id,valve_state_str))
        # check if state already as asked and warn if it is the case
        previous_valve_state = self.device.read_valve_state(valve_id)
        while previous_valve_state is None:
            logging.warning('reading Valve %s state not successful, trying again' % valve_id)
            previous_valve_state = self.device.read_valve_state(valve_id)
        if previous_valve_state == valve_state:
            logging.warning('useless (state already as asked) command asked Valve %s %s, so not doing it' % (valve_id,valve_state_str))
            return
        # send command, check success, if not try again until success
        self.device.send_valve_command(valve_id, valve_state)
        sleep(0.01)
        while self.device.read_valve_state(valve_id) != valve_state:
            logging.warning('T= %f | command Valve %s %s not successful, trying again' % (time(),valve_id, {0:'OFF', 1:'ON'}[valve_state]))
            self.device.send_valve_command(valve_id, valve_state)
            sleep(0.01)
        logging.info('T= %f | finished for command Valve %s %s' % (time(),valve_id, {0:'OFF', 1:'ON'}[valve_state]))

    ## function to open a valve for a fixed duration (using threading.Timer)
    def open_valve_for_duration(self, valve_id, duration_s, blocking=False, wait_after=0.):
        if self.virtual_mode:
            self.log_item('VALVE', f'VALVE {valve_id} ACTIVE FOR {duration_s}')
            return
        if not self.is_active():
            raise Exception('Manager is not active ?')
        logging.info('T= %f | asked for opening Valve %s for duration %f seconds' % (time(),valve_id, duration_s))
        if duration_s < 0.1:
            logging.warning('Asked for opening Valve %s for too short duration (%f), not doing it' % (valve_id, duration_s))
        self.set_valve_state(valve_id, True)
        close_thread = threading.Timer(duration_s, self.set_valve_state, (valve_id, False))
        close_thread.start()
        if blocking:
            close_thread.join()
            sleep(wait_after)
        return close_thread

    ## function to read the state of a valve
    def get_valve_state(self, valve_id):
        if not self.is_active():
            raise Exception('Manager is not active ?')
        logging.info('T= %f | asked for reading state of Valve %s' % (time(),valve_id))
        valve_state = self.device.read_valve_state(valve_id)
        while valve_state is None:
            logging.warning('reading Valve %s state not successful, trying again' % valve_id)
            valve_state = self.device.read_valve_state(valve_id)
        logging.info('T= %f | state of Valve %s is %s' % (time(),valve_id,valve_state))
        return valve_state

    ## function to perform turbidity readings
    def get_turbidity_readings(self, turbi_set_ids, n_measurements=6, n_exclude_high=0, wait_time_btw_measurements=4, apply_calibration=True):
        if self.virtual_mode:
            self.log_item('OD', f'OD request for sets {turbi_set_ids}')
            return {rid:0.5 for rid in range(17)} # to improve later
        if not self.is_active():
            raise Exception('Manager is not active ?.')
        if self.use_wago_only:
            raise Exception('Wago only session.')
        logging.info('T= %f | asked for turbidity readings for turbi sets %s' % (time(), str(turbi_set_ids)))
        # do measurements
        all_readings = {turbi_set_id:[] for turbi_set_id in turbi_set_ids}
        for i in range(n_measurements):
            # iterate on turbi sets
            for turbi_set_id in turbi_set_ids:
                # ask for the readings
                self.device.send_turbidity_command(turbi_set_id)
                # retrieve the response
                readings_this = self.device.receive_turbidity_readings(turbi_set_id)
                readings_str = ' '.join(['R'+str(turbi_id) + '= ' + str(readings_this[turbi_id]) for turbi_id in readings_this])
                logging.info('T= %f | received turbidity readings for turbi set %i: %s' % (time(), turbi_set_id, readings_str))
                all_readings[turbi_set_id].append(readings_this)
            # wait before next round of measurements
            if i < n_measurements - 1:
                sleep(wait_time_btw_measurements)
        # compute average of readings
        avg_readings = {}
        for turbi_set_id in turbi_set_ids:
            for vessel_slot_id in all_readings[turbi_set_id][0]:
                if n_exclude_high > 0:
                    avg_readings[vessel_slot_id] = np.mean(sorted([readings[vessel_slot_id] for readings in all_readings[turbi_set_id]])[:-n_exclude_high])
                else:
                    avg_readings[vessel_slot_id] = np.mean([readings[vessel_slot_id] for readings in all_readings[turbi_set_id]])
        logging.info('T= %f | computed average of %i turbidity readings after excluding %i highest %s' % (time(), n_measurements, n_exclude_high, str(avg_readings)))
        # apply calibration if asked for, return readings / ods
        if not apply_calibration:
            return avg_readings
        else:
            od_values = {}
            for vessel_slot_id in avg_readings:
                od =  self.od_calib_pars.loc[vessel_slot_id]['slope']*np.log(avg_readings[vessel_slot_id])+self.od_calib_pars.loc[vessel_slot_id]['intercept']
                if od > 2:
                    od = 2
                od_values[vessel_slot_id] = od
            logging.info('T= %f | applied calibration on turbidity readings average %s' % (time(), str(od_values)))
            return od_values

    ## function to shut-off all coils
    def shut_off_all_pumps_and_valves(self):
        if self.virtual_mode:
            self.log_item('GLOBAL','SHUT OFF ALL PUMPS AND VALVES')
            return
        if not self.is_active():
            raise Exception('Manager is not active ?')
        logging.info('T= %f | asked for shutting off all pumps and valves' % (time()))
        # check if state already as asked and warn if case
        previous_coils_state = self.device.read_all_coils()
        while previous_coils_state is None:
            logging.warning('reading all coils not successful, trying again')
            previous_coils_state = self.device.read_all_coils()
        if not any(previous_coils_state):
            logging.warning('useless shut off all coils, already all off, not doing anything')
            return
        # send command, check success, if not try again until success
        self.device.send_coils_shutoff_command()
        sleep(0.01)
        while any(self.device.read_all_coils()):
            logging.warning('T= %f | shut off all coils command not successful, trying again' % time())
            self.device.send_coils_shutoff_command()
            sleep(0.01)
        # finished !
        logging.info('T= %f | finished shut off all coils command' % time())

    ## function to shut off all LEDs
    def shut_off_all_LEDs(self):
        if self.virtual_mode:
            self.log_item('LIGHT', 'SHUT OF ALL LEDS')
        if not self.is_active():
            raise Exception('Manager is not active ?')
        logging.info('T= %f | asked for shutting off all LEDs' % (time()))
        # shutting of leds
        self.device.leds_request('turn_off_all')
        # finished !
        logging.info('T= %f | finished shut off all LEDs command' % time())

    ## function to change the LEDs intensity
    def set_leds_intensity(self, reactor_id, intensity):
        if self.virtual_mode:
            self.log_item('LIGHT', f'LEDS REACTOR {reactor_id} INTENSITY {intensity}')
            return
        if not self.is_active():
            raise Exception('Manager is not active ?')
        if self.use_wago_only:
            raise Exception('Wago only session.')
        logging.info('T= %f | asked for setting LEDs intensity for reactor %i to %i' % (time(), reactor_id, intensity))
        self.device.leds_request(f'reset_schedule/{reactor_id}')
        self.device.leds_request(f'schedule/{reactor_id}/{intensity}')
        logging.info('T= %f | command for setting LEDs intensity of reactor %i to %i has been sent' % (time(), reactor_id, intensity))

    def schedule_leds_change(self, reactor_id, intensity, delta_t_seconds):
        intensity = int(intensity)
        if self.virtual_mode:
            self.log_item('LIGHT', f'LEDS REACTOR {reactor_id} SCHEDULE CHANGE TO INTENSITY {intensity} IN {delta_t_seconds} SECONDS')
            return
        if not self.is_active():
            raise Exception('Manager is not active ?')
        if self.use_wago_only:
            raise Exception('Wago only session.')
        logging.info('T= %f | asked for setting LEDs intensity for reactor %i to %i in %f' % (time(), reactor_id, intensity, delta_t_seconds))
        self.device.leds_request(f'schedule/{reactor_id}/{intensity}/{delta_t_seconds}')
        logging.info('T= %f | command for setting LEDs intensity of reactor %i to %i in %f has been sent' % (time(), reactor_id, intensity, delta_t_seconds))

    def set_leds_duty_cycle(self, reactor_id, intensity, period_seconds, fraction, cycle_number):
        if self.virtual_mode:
            self.log_item('LIGHT',
            f'LEDS REACTOR {reactor_id} DUTY CYCLE INTENSITY {intensity} PERIOD {period_seconds} SECONDS FRACTION {fraction} CYCLE NUMBER {cycle_number}')
            return
        if not self.is_active():
            raise Exception('Manager is not active ?')
        if self.use_wago_only:
            raise Exception('Wago only session.')
        logging.info('T= %f | asked for setting LEDs duty cycle for reactor %i to intensity %i with period %f seconds, fraction %f and cycle number %f' % (time(), reactor_id, intensity, period_seconds, fraction, cycle_number))
        self.device.leds_request(f'duty_cycling/{reactor_id}/{intensity}/{period_seconds}/{fraction}/{cycle_number}')
        logging.info('T= %f | command for setting LEDs duty cycle for reactor %i to intensity %i with period %f seconds, fraction %f and cycle number %f sent' % (time(), reactor_id, intensity, period_seconds, fraction, cycle_number))

    def get_leds_history(self, reactor_id, t_start=0):
        if self.virtual_mode:
            self.log_item('LIGHT', f'LEDS HISTORY REACTOR {reactor_id} FROM T={t_start}')
            return
        if not self.is_active():
            raise Exception('Manager is not active ?')
        if self.use_wago_only:
            raise Exception('Wago only session.')
        logging.info('T= %f | asked for LEDs duty history reactor %i from time %f' % (time(), reactor_id, t_start))
        history_str = self.device.leds_request(f'history/{reactor_id}/{t_start}')
        if '@' not in history_str:
            return []
        return sorted([(float(ch_str.split('@')[0]),int(ch_str.split('@')[1])) for ch_str in history_str.split('_')[1:]], key=lambda x: x[0])
        logging.info('T= %f | command for LEDs duty history reactor %i from time %f sent' % (time(), reactor_id, t_start))

    def get_all_leds_history(self, t_start=0):
        if self.virtual_mode:
            self.log_item('LIGHT', f'LEDS HISTORY ALL REACTORS FROM T={t_start}')
            return
        if not self.is_active():
            raise Exception('Manager is not active ?')
        if self.use_wago_only:
            raise Exception('Wago only session.')
        logging.info('T= %f | asked for LEDs duty history all_reactors from time %f' % (time(), t_start))
        all_history_str = self.device.leds_request(f'history/all/{t_start}')
        rid = 0
        all_histories = {}
        for history_str in all_history_str.split('|'):
            rid += 1
            if '@' not in history_str:
                all_histories[rid] = []
            else:
                all_histories[rid] = sorted([(float(ch_str.split('@')[0]),int(ch_str.split('@')[1])) for ch_str in history_str.split('_')[1:]], key=lambda x: x[0])
        return all_histories
        logging.info('T= %f | command for LEDs duty history all reactors from time %f sent' % (time(), t_start))

    ## flask request to ot2
    def send_ot2_request(self, endpoint):
        if self.virtual_mode:
            self.log_item('OT2', f'OT2 {endpoint}')
            return
        logging.info('T= %f | sending request %s to the ot2' % (time(), endpoint))
        response = self.device.ot2_request(endpoint)
        logging.info('T= %f | Finished request %s to the ot2' % (time(), endpoint))
        return response

    ## flask request to guava
    def send_guava_request(self, endpoint, is_file=False):
        if self.virtual_mode:
            self.log_item('GUAVA', f'GUAVA {endpoint}')
            return
        logging.info('T= %f | sending request %s to the guava' % (time(), endpoint))
        response = self.device.guava_request(endpoint, is_file)
        logging.info('T= %f | Finished request %s to the guava' % (time(), endpoint))
        return response
