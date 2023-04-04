import numpy as np
import pandas as pd
from time import time
from datetime import date, timedelta
import os
import json
from matplotlib import pyplot as plt

# base class to represent a program running in one experiment
class Program:
    def __init__(self, user, campaign, short_name, description, reactor_id, preculture, media,
                position_drain_output_mL=20.,
                position_sampling_output_mL=5.,
                creation_date_shift=None, blank=None, vessel_id=0):
        self.user = user
        self.campaign = campaign
        self.short_name = short_name.replace(' ', '_')
        self.description = description
        self.reactor_id = reactor_id
        self.preculture = preculture
        self.active_cytometry = False
        self.renew_sampled_volume = False
        self.position_drain_output_mL = position_drain_output_mL
        self.position_sampling_output_mL = position_sampling_output_mL
        self.start_volume_mL = self.position_drain_output_mL
        self.dead_volume_sampling_line_mL = 2.5
        self.media = media
        if blank is None:
            self.blank = None
            self.blanks = {'time_s':[], 'blank_OD':[]}
        else:
            self.blank = blank
            self.blanks = {'time_s':[0]*5, 'blank_OD':[blank]*5}
        self.ODs = {'time_s':[], 'OD':[]}
        self.dilutions = {'time_s':[], 'duration_s':[], 'est_flow_rate_uL_per_s':[]}
        self.LEDs = {'time_s':[], 'intensity':[]}
        self.samplings = {'time_s':[], 'guava_well':[], 'guava_fcs_file':[], 'sampling_plate_and_col':[]}
        self.cells = None
        self.events = []
        self.drain_out_pump_duration_s = 12.
        self.vessel_id = vessel_id
        if creation_date_shift:
            self.creation_date = str(date.today()-timedelta(days=creation_date_shift))
        else:
            self.creation_date = str(date.today())
        if os.path.isdir(self.output_path):
            yes_no = input('Already existing ! Is this a restart of ongoing experiment ? If yes, will reload data and blank. [y/n].')
            if yes_no != 'y':
                raise Exception('User indicates its not restart but program output folder already existing ? change exp short name ?')
            self.load()
        else:
            if os.path.isdir(self.atlas_path):
                raise Exception('This program exist in ATLAS, but not locally ? WTF ? Aborting')
            os.makedirs(self.output_path)
            os.makedirs(self.atlas_path)
            self.save_program_description(path=self.output_path)
            self.save_program_description(path=self.atlas_path)
        self.init_time = time()
        self._manager = None
    def give_program_description(self):
        dct = {'preculture':self.preculture.to_dict(), 'media':self.media, 'reactor_id':self.reactor_id,
                'user':self.user, 'campaign':self.campaign,
                'short_name':self.short_name, 'description':self.description,
                'creation_date':self.creation_date,
                'position_drain_output_mL':self.position_drain_output_mL,
                'start_volume_mL':self.start_volume_mL,
                'position_sampling_output_mL':self.position_sampling_output_mL,
                'dead_volume_sampling_line_mL':self.dead_volume_sampling_line_mL,
                'vessel_id':self.vessel_id}
        for k,v in self.give_program_parameters().items():
            dct[k] = v
        return dct
    def save_program_description(self, path):
        dct = self.give_program_description()
        with open(f'{path}/program_description.json', 'w') as out_json_f:
            json.dump(dct, out_json_f, sort_keys=True, indent=4)
    def load(self, ignore_new=False):
        if not ignore_new:
            dct_new = self.give_program_description()
        with open(f'{self.output_path}/program_description.json', 'r') as in_json_f:
            dct = json.load(in_json_f)
        if not ignore_new and dct != dct_new:
            print('Reloading program with different description as the newly given one ! Be careful...')
        for k in ['user', 'campaign', 'short_name', 'description', 'reactor_id', 'creation_date', 'position_drain_output_mL', 'position_sampling_output_mL', 'start_volume_mL', 'media', 'dead_volume_sampling_line_mL', 'vessel_id']:
            if k in dct:
                setattr(self, k, dct[k])
            else:
                print(f'metadata {k} not in program description ?')
        self.preculture = Preculture(strain_name=dct['preculture']['strain_name'],
                                    strain_id=dct['preculture']['strain_id'],
                                    media=dct['preculture']['media'])
        # program parameters
        for k in self.give_program_parameters():
            setattr(self, k, dct[k])
        # recover data
        for data_name in ['blanks', 'ODs', 'LEDs', 'dilutions', 'samplings']:
            if os.path.isfile(f'{self.output_path}/{data_name}.csv'):
                pd_data = pd.read_csv(f'{self.output_path}/{data_name}.csv')
                setattr(self, data_name, pd_data.to_dict(orient='list'))
        if os.path.isfile(f'{self.output_path}/cells.csv'):
            self.cells = pd.read_csv(f'{self.output_path}/cells.csv')
    @property
    def output_path(self):
        return f'experiment-data/{self.user}/{self.campaign}/{self.creation_date}_{self.short_name}/reactor-data/reactor-{self.reactor_id}'
    @property
    def atlas_path(self):
        return f'Z:experiments/bioreactors/{self.user}/{self.campaign}/{self.creation_date}_{self.short_name}/reactor-data/reactor-{self.reactor_id}'
    def give_program_parameters(self):
        return {}
    def receive_OD_reading(self, OD_reading):
        # if blank phase not finished
        if len(self.blanks['blank_OD']) < 5:
            self.blanks['time_s'].append(time())
            self.blanks['blank_OD'].append(OD_reading)
        # if last blank
        if len(self.blanks['blank_OD']) == 5 and self.blank is None:
            self.blank = np.mean(self.blanks['blank_OD'])
        # normal case
        if not self.blank is None:
            self.ODs['time_s'].append(time())
            self.ODs['OD'].append(OD_reading - self.blank)
    def has_OD_measurements(self):
        return len(self.ODs['OD']) > 0
    def give_last_OD(self):
        return self.ODs['OD'][-1]
    def set_LED(self, led_intensity):
        self._manager.set_leds_intensity(self.reactor_id, led_intensity)
    def schedule_LED_change(self, led_intensity, delta_t_seconds):
        self._manager.schedule_leds_change(self.reactor_id, led_intensity, delta_t_seconds)
    def start_LED_duty_cycle(self, intensity, period_seconds, fraction, cycle_number):
        self._manager.set_leds_duty_cycle(self.reactor_id, intensity, period_seconds, fraction, cycle_number)
    def update_LED_data(self, changes):
        if self.LEDs['time_s']:
            t_start = max(self.LEDs['time_s'])
        else:
            t_start = self.init_time
        new_changes = [(rct,intensity) for rct,intensity in changes if rct > t_start]
        for real_change_time,led_intensity in new_changes:
            self.LEDs['time_s'].append(real_change_time)
            self.LEDs['intensity'].append(led_intensity)
    @property
    def growth_rates(self):
        dil = self.data_to_df('dilutions')
        od = self.data_to_df('ODs')
        delta_dils = dil['time_s'].diff()
        I_dil_start = delta_dils > 900.
        prev = False
        growth_phases = []
        for k,v in I_dil_start.items():
            if v:
                t1 = dil['time_s'].iloc[k-1]
                t2 = dil['time_s'].iloc[k]
                growth_phases.append((t1,t2))
        growth_rate_per_hr = []
        time_s = []
        for t1,t2 in growth_phases:
            try:
                od_phase = od[(od['time_s']>t1) & (od['time_s']<t2)]
                if od_phase['OD'].max() - od_phase['OD'].min() > 0.05 and od_phase['OD'].diff().max() < 0.04:
                    pfit = np.polyfit(od_phase['time_s']/3600., np.log(od_phase['OD']), 1)
                    time_s.append((t1+t2)/2)
                    growth_rate_per_hr.append(pfit[0])
            except:
                pass
        return pd.DataFrame.from_dict({'growth_rate_per_hr':growth_rate_per_hr,
                                       'time_s':time_s})
    @property
    def volume_estimates(self):
        samplings = self.data_to_df('samplings')
        dilutions = self.data_to_df('dilutions')
        dead_volume_mL = self.dead_volume_sampling_line_mL
        current_volume_mL = self.start_volume_mL
        min_volume_mL = self.position_sampling_output_mL
        max_volume_mL = self.position_drain_output_mL
        t = []
        V = []
        i_s = 0
        i_d = 0
        while i_s < len(samplings) or i_d < len(dilutions):
            if i_s < len(samplings) and i_d < len(dilutions):
                t_s = samplings.iloc[i_s]['time_s']
                t_d = dilutions.iloc[i_d]['time_s']
                if t_s < t_d:
                    t += [t_s,t_s]
                    V.append(current_volume_mL)
                    current_volume_mL -= dead_volume_mL
                    if current_volume_mL < min_volume_mL:
                        current_volume_mL = min_volume_mL
                    V.append(current_volume_mL)
                    i_s += 1
                else:
                    t += [t_d,t_d]
                    V.append(current_volume_mL)
                    current_volume_mL += dilutions.iloc[i_d]['duration_s'] * dilutions.iloc[i_d]['est_flow_rate_uL_per_s'] / 1000.
                    if current_volume_mL > max_volume_mL:
                        current_volume_mL = max_volume_mL
                    V.append(current_volume_mL)
                    i_d += 1
            else:
                if i_s < len(samplings):
                    t_s = samplings.iloc[i_s]['time_s']
                    t += [t_s,t_s]
                    V.append(current_volume_mL)
                    current_volume_mL -= dead_volume_mL
                    if current_volume_mL < min_volume_mL:
                        current_volume_mL = min_volume_mL
                    V.append(current_volume_mL)
                    i_s += 1
                else:
                    t_d = dilutions.iloc[i_d]['time_s']
                    t += [t_d,t_d]
                    V.append(current_volume_mL)
                    current_volume_mL += dilutions.iloc[i_d]['duration_s'] * dilutions.iloc[i_d]['est_flow_rate_uL_per_s'] / 1000.
                    if current_volume_mL > max_volume_mL:
                        current_volume_mL = max_volume_mL
                    V.append(current_volume_mL)
                    i_d += 1
        return pd.DataFrame.from_dict({'time_s':t, 'volume_estimation_mL':V})
    def data_to_df(self, data_name):
        return pd.DataFrame.from_dict(getattr(self, data_name))
    def all_data_to_dfs(self):
        return {data_name:self.data_to_df(data_name) for data_name in ['blanks', 'ODs', 'LEDs', 'dilutions', 'samplings', 'growth_rates', 'volume_estimates']}
    def plot(self, axs=None, show_fl=False, ch_fl='GRN-B-HLin'):
        # method to plot together: LED history, OD history, growth rate history
        # choose color from reactor id
        color = plt.cm.jet(np.linspace(0,1,16))[self.reactor_id-1]
        # build subplot
        if axs is None:
            if not show_fl:
                f, (ax_OD, ax_gr, ax_LEDs) = plt.subplots(ncols=1, nrows=3, figsize=(15,15))
            else:
                f, (ax_OD, ax_gr, ax_LEDs, ax_fl) = plt.subplots(ncols=1, nrows=4, figsize=(15,20))
        else:
            if not show_fl:
                ax_OD, ax_gr, ax_LEDs = axs
            else:
                ax_OD, ax_gr, ax_LEDs, ax_fl = axs
        # data
        df_ODs = self.data_to_df('ODs')
        df_LEDs = self.data_to_df('LEDs')
        df_grs = self.data_to_df('growth_rates')
        if show_fl:
            df_fl = self.cells.groupby('time_s').median()
        # for LED data, we have only the time of change, let's make it a proper time series
        if not df_LEDs.empty:
            t0_LEDs = min([df_LEDs['time_s'].iloc[0],df_ODs['time_s'].iloc[0]]) - 2
            t_minus = [t-1 for t in df_LEDs['time_s']]
            intensity_minus = [0] + [intensity for intensity in df_LEDs['intensity'].iloc[:-1]]
            t = [t0_LEDs] + t_minus + [df_LEDs['time_s'].iloc[-1], df_ODs['time_s'].iloc[-1]]
            intensity = [0] + intensity_minus + [df_LEDs['intensity'].iloc[-1]]*2
        else:
            t = [df_ODs['time_s'].iloc[0],df_ODs['time_s'].iloc[-1]]
            intensity = [0,0]
        df_LEDs = df_LEDs.append(pd.DataFrame.from_dict({'time_s':t, 'intensity':intensity}), ignore_index=True)
        df_LEDs = df_LEDs.sort_values('time_s').reset_index()
        # use OD time 0 as time ref
        t0 = df_ODs['time_s'].iloc[0]
        for df in [df_ODs, df_LEDs, df_grs]:
            df['rel_time_hrs'] = (df['time_s'] - t0) / 3600.
        if show_fl:
            df_fl['rel_time_hrs'] = (df_fl.index - t0) / 3600.
        # reactor label
        reactor_label = f'reactor {self.reactor_id} - {self.preculture.strain_name}({self.preculture.strain_id})'
        # plot OD
        ax_OD.plot(df_ODs['rel_time_hrs'], df_ODs['OD'], color=color, label=reactor_label)
        ax_OD.set_xlabel('Time (hrs)')
        ax_OD.set_ylabel('OD')
        ax_OD.legend()
        # plot growth rate
        ax_gr.plot(df_grs['rel_time_hrs'], df_grs['growth_rate_per_hr'], '-o', color=color)
        ax_gr.set_xlabel('Time (hrs)')
        ax_gr.set_ylabel('Growth rate (per hr)')
        ax_gr.set_ylim([0,0.5])
        # plot leds
        ax_LEDs.plot(df_LEDs['rel_time_hrs'], df_LEDs['intensity'], color=color, label=reactor_label)
        ax_LEDs.set_xlabel('Time (hrs)')
        ax_LEDs.set_ylabel('LED intensity')
        ax_LEDs.legend()
        # plot fl
        if show_fl:
            ax_fl.plot(df_fl['rel_time_hrs'], df_fl[ch_fl], '-o', color=color)
        # consistent xlims for all plots
        for ax in [ax_OD, ax_gr, ax_LEDs]:
            ax.set_xlim([0,df_ODs['rel_time_hrs'].iloc[-1]+1])
        if show_fl:
            ax_fl.set_xlim([0,df_ODs['rel_time_hrs'].iloc[-1]+1])
        # return ax objects for further tweaking style by user
        if not show_fl:
            return ax_OD, ax_gr, ax_LEDs
        else:
            return ax_OD, ax_gr, ax_LEDs, ax_fl
    def plot_all_cells(self, ch_fl='GRN-B-HLin',ax=None,ylim=(1,30000),delta_i_per_hr=1000,log_scale=True,filter_str=None,down_sampling=None):
        if ax is None:
            f,ax = plt.subplots(figsize=(14,8), ncols=1, nrows=1)
        if filter_str is not None:
            cells = self.cells.query(filter_str).reset_index()
        else:
            cells = self.cells
        n_tp = len(cells.groupby('time_s'))
        colors = plt.cm.jet(np.linspace(0,1,n_tp))
        i_tp = 0
        delta_i = 0
        cum_i = 0
        tp_prev = cells['time_s'].iloc[0]
        for tp,d in cells.groupby('time_s'):
            delta_i += (tp-tp_prev) / 3600 * delta_i_per_hr
            if down_sampling is not None:
                d = d.iloc[-down_sampling:]
            ax.scatter(np.arange(len(d)) + cum_i + delta_i, d[ch_fl], s=0.1, c=np.array([colors[i_tp]]))
            tp_prev = tp
            cum_i += len(d)
            i_tp += 1
        ax.set_title(f'reactor {self.reactor_id} - {self.preculture.strain_name}({self.preculture.strain_id})')
        ax.set_ylim(ylim)
        ax.set_ylabel(ch_fl)
        if log_scale:
            ax.set_yscale('log')
        return ax



class TurbidostatProgram(Program):
    def __init__(self, user, campaign, short_name, description, reactor_id, preculture, media,
    OD_setpoint, position_drain_output_mL=20., position_sampling_output_mL=5., creation_date_shift=None, blank=None, vessel_id=0):
        self.base_dilution_duration = 3.
        self.est_flow_rate_uL_per_s = 250.
        self.OD_setpoint = OD_setpoint
        super().__init__(user, campaign, short_name, description, reactor_id, preculture, media,position_drain_output_mL, position_sampling_output_mL, creation_date_shift, blank, vessel_id)
    def give_program_parameters(self):
        return {'OD_setpoint':self.OD_setpoint}
    def compute_dilution_duration(self):
        if (self.blank is not None) and self.has_OD_measurements() and (self.give_last_OD() > self.OD_setpoint):
            self.dilutions['time_s'].append(time())
            self.dilutions['duration_s'].append(self.base_dilution_duration)
            self.dilutions['est_flow_rate_uL_per_s'].append(self._manager.input_pump_flow_rate_mL_min(self.reactor_id)/60.*1000.)
            return self.dilutions['duration_s'][-1]
        else:
            return None

class GrowDiluteProgram(TurbidostatProgram):
    def __init__(self, user, campaign, short_name, description, reactor_id, preculture, media, OD_low, OD_high,
                position_drain_output_mL=20., position_sampling_output_mL=5., creation_date_shift=None, blank=None, vessel_id=0):
        if OD_low >= OD_high:
            raise Exception('OD_low >= OD_high !!!!! Does not make sense.')
        self.est_flow_rate_uL_per_s = 250.
        self.OD_low = OD_low
        self.OD_high = OD_high
        super().__init__(user, campaign, short_name, description, reactor_id, preculture, media, OD_high, position_drain_output_mL, position_sampling_output_mL, creation_date_shift, blank, vessel_id)
        self.base_dilution_duration = 6.
    def give_program_parameters(self):
        return {'OD_low':self.OD_low, 'OD_high':self.OD_high}
    def compute_dilution_duration(self):
        # compute dilution duration
        dur = super().compute_dilution_duration()
        # check if should change mode
        if self.blank is not None:
            # deal with not correct setpoint (could happen if changed manually)
            if self.OD_setpoint not in [self.OD_low, self.OD_high]:
                self.OD_setpoint = self.OD_high
            # change from high to low if we are in growth phase and passed the setpoint
            if self.OD_setpoint == self.OD_high and self.give_last_OD() > self.OD_high:
                self.OD_setpoint = self.OD_low
            # change from low to high if we are in dilution phase and passed the setpoint
            if self.OD_setpoint == self.OD_low and self.give_last_OD() < self.OD_low:
                self.OD_setpoint = self.OD_high
        # return the duration to compute
        return dur

class Preculture:
    def __init__(self, strain_id, media, strain_name = None):
        self.strain_id = strain_id
        self.media = media
        self.strain_name = strain_name
    def to_dict(self):
        return {'strain_id':self.strain_id, 'media':self.media, 'strain_name':self.strain_name}
