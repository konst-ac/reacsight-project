from cytoreactors.design.program import Program
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

class ReactorData(Program):
    def __init__(self, data_path):
        self.data_path = data_path
        self.load()
        # keep only as dataframes
        dfs = self.all_data_to_dfs()
        self.ODs = dfs['ODs']
        self.growth_rates_ = dfs['growth_rates']
        self.LEDs = dfs['LEDs']
        self.LEDs_changes = None
        self.dilutions = dfs['dilutions']
        self.samplings = dfs['samplings']
        self.volume_estimates_ = dfs['volume_estimates']
        # treat the LEDs to be state vs time rather than time of change
        if not self.LEDs.empty:
            t0_LEDs = min([self.LEDs['time_s'].iloc[0],self.ODs['time_s'].iloc[0]]) - 2
        else:
            t0_LEDs = self.ODs['time_s'].iloc[0]
        ts = [t0_LEDs]
        intensities = [0]
        t_changes = []
        intensity_changes = []
        for _,row in self.LEDs.iterrows():
            if row['intensity'] != intensities[-1]:
                ts += [row['time_s'], row['time_s']]
                intensities += [intensities[-1], row['intensity']]
                t_changes += [row['time_s']]
                intensity_changes += [row['intensity']]
        if ts[-1] < self.ODs['time_s'].iloc[-1]:
            ts.append(self.ODs['time_s'].iloc[-1])
            intensities.append(intensities[-1])
        self.LEDs = pd.DataFrame.from_dict({'time_s':ts, 'intensity':intensities})
        dfs['LEDs'] = self.LEDs
        self.LEDs_changes = pd.DataFrame.from_dict({'time_s':t_changes, 'intensity':intensity_changes})
        # compute relative time in hrs vs first OD measurement if no light or first light if there is light
        if self.LEDs_changes.empty:
            t0 = self.ODs['time_s'].iloc[0]
        else:
            t0 = self.LEDs_changes['time_s'].iloc[0]
        self.change_t0(t0)
    def change_t0(self, t0):
        self.t0 = t0
        for df in [self.ODs, self.dilutions, self.growth_rates_, self.LEDs, self.LEDs_changes, self.samplings, self.volume_estimates_]:
            df['rel_time_hrs'] = (df['time_s'] - self.t0) / 3600.
        if hasattr(self, 'cells'):
            self.cells['rel_time_hrs'] = (self.cells['time_s'] - self.t0) / 3600.
            self.cells['sampling_rel_time_hrs'] = (self.cells['sampling_time_s'] - self.t0) / 3600.
    @property
    def growth_rates(self):
        if hasattr(self, 'growth_rates_'):
            return self.growth_rates_
        return super().growth_rates
    @property
    def volume_estimates(self):
        if hasattr(self, 'volume_estimates_'):
            return self.volume_estimates_
        return super().volume_estimates
    def load(self):
        super().load(ignore_new=True)
        if not hasattr(self, 'dead_volume_sampling_line_mL'):
            self.dead_volume_sampling_line_mL = 4.5
        if not hasattr(self, 'start_volume_mL'):
            self.start_volume_mL = 20.
        if not hasattr(self, 'position_sampling_output_mL'):
            self.position_sampling_output_mL = 5.
        if not hasattr(self, 'position_drain_output_mL'):
            self.position_drain_output_mL = 20.
    def compute_LED_duty_fraction_traj(self, min_duration_cycle_s=0):
        effective_intensities = []
        ts = []
        current_intensity = 0
        ongoing_cycle = False
        for _,row in self.LEDs_changes.iterrows():
            row_intensity,row_time_s = row['intensity'],row['time_s']
            #print(f'{row_time_s} -- {row_intensity} [{ongoing_cycle}, {current_intensity}]')
            if ongoing_cycle:
                # case where we start the OFF phase of cycle
                if current_intensity > 0 and row['intensity'] == 0:
                    on_duration_s = row['time_s'] - current_start
                    current_start = row['time_s']
                    intensity = current_intensity
                    current_intensity = 0
                # case when we finish the OFF phase of the cycle
                if current_intensity == 0 and row['intensity'] > 0:
                    off_duration_s = row['time_s'] - current_start
                    cycle_duration_s = on_duration_s + off_duration_s
                    effective_intensity = intensity * on_duration_s / cycle_duration_s
                    current_start = row['time_s']
                    if cycle_duration_s > min_duration_cycle_s:
                        ts += [t_cycle_start, current_start]
                        effective_intensities += [effective_intensity, effective_intensity]
                    current_intensity = row['intensity']
                    t_cycle_start = current_start
                # case when change of intensity that is not OFF
                if current_intensity > 0 and row['intensity'] > 0:
                    if current_intensity != row['intensity']:
                        raise Exception('case not handled: change of intensity from >0 to other >0')
            else:
                if row['intensity'] > 0:
                    ongoing_cycle = True
                    current_start = row['time_s']
                    current_intensity = row['intensity']
                    t_cycle_start = current_start
        if not ts:
            raise Exception('no full cycle ?')
        ts = np.array(ts)
        rel_t_hrs = (ts - self.ODs['time_s'].iloc[0])/3600.
        effective_intensities = np.array(effective_intensities) / 40.
        return pd.DataFrame.from_dict({'time_s':ts, 'duty_fraction':effective_intensities, 'rel_time_hrs':rel_t_hrs})
    @property
    def output_path(self):
        return self.data_path


class ReactorGroup:
    def __init__(self, reactor_ids, reactor_data_path = '../reactor-data'):
        self.reactor_data_path = reactor_data_path
        self.reactor_ids = reactor_ids
        self.all_data = {}
        self.load()
    def load(self):
        for rid in self.reactor_ids:
            self.all_data[rid] = ReactorData(f'{self.reactor_data_path}/reactor-{rid}')
    def reactor(self, reactor_id):
        return self.all_data[reactor_id]
    def plot_OD(self, ax=None):
        if ax is None:
            f,ax = plt.subplots(ncols=1, nrows=1, figsize=(15,6))
        for rid,data in self.all_data.items():
            df_od = data.data_to_df('ODs')
            df_od['rel_time_hrs'] = (df_od['time_s'] - df_od['time_s'].iloc[0])/3600
            color = plt.cm.jet(np.linspace(0,1,16))[rid-1]
            ax.plot(df_od['rel_time_hrs'], df_od['OD'], color=color,  label=f'{rid}')
        ax.legend()
        ax.grid()
        return ax
    def plot_growth_rates(self, ax=None):
        if ax is None:
            f,ax = plt.subplots(ncols=1, nrows=1, figsize=(15,6))
        for rid,data in self.all_data.items():
            df_od = data.data_to_df('ODs')
            df_gr = data.data_to_df('growth_rates')
            df_gr['rel_time_hrs'] = (df_gr['time_s'] - df_od['time_s'].iloc[0])/3600
            color = plt.cm.jet(np.linspace(0,1,16))[rid-1]
            ax.plot(df_gr['rel_time_hrs'], df_gr['growth_rate_per_hr'], '-o', color=color,  label=f'{rid}')
        ax.legend()
        ax.grid()
        return ax
    def plot_fl(self, ax=None, ch_fl='GRN-B-HLin'):
        if ax is None:
            f,ax = plt.subplots(ncols=1, nrows=1, figsize=(15,6))
        for rid,data in self.all_data.items():
            df_od = data.data_to_df('ODs')
            if ch_fl not in data.cells.columns:
                if ch_fl.startswith('ratio_'):
                    ch_1 = ch_fl.split('ratio_')[1].split('_')[0]
                    ch_2 = ch_fl.split('ratio_')[1].split('_')[1]
                    data.cells[ch_fl] = data.cells[ch_1] / data.cells[ch_2]
            df_cells = data.cells.groupby('time_s').median()
            df_cells['rel_time_hrs'] = (df_cells.index - df_od['time_s'].iloc[0])/3600
            color = plt.cm.jet(np.linspace(0,1,16))[rid-1]
            ax.plot(df_cells['rel_time_hrs'], df_cells[ch_fl], '-o', color=color,  label=f'{rid}')
        ax.legend()
        ax.grid()
        ax.set_ylabel(f'median {ch_fl}')
        return ax
    def plot_generic(self, reac_plot_fun, ax=None):
        if ax is None:
            f,ax = plt.subplots(ncols=1, nrows=1, figsize=(15,6))
        for rid,data in self.all_data.items():
            color = plt.cm.jet(np.linspace(0,1,16))[rid-1]
            reac_plot_fun(ax=ax,data=data,color=color, label=f'{rid}')
        ax.legend()
        ax.grid()
        return ax


from os import walk, path
import json
def findAllReactorDataOfStrain(strain_id, root_to_atlas='Z:'):
    matches = []
    for root,dirs,files in walk(f'{root_to_atlas}/experiments/bioreactors/'):
        for dirname in dirs:
            if dirname != 'reactor-data' and dirname.startswith('reactor-'):
                desc_fname = path.join(root, dirname, 'program_description.json')
                if path.exists(desc_fname):
                    with open(path.join(root, dirname, 'program_description.json'), 'r') as f:
                        desc = json.load(f)
                        strain_id_this = desc['preculture']['strain_id']
                        if strain_id_this == strain_id:
                            matches.append({'root':path.join(root,dirname), 'metadata':desc})
    matches_by_creation_date = {}
    for match in matches:
        creation_date = match['metadata']['creation_date']
        if creation_date in matches_by_creation_date:
            matches_by_creation_date[creation_date].append(match)
        else:
            matches_by_creation_date[creation_date] = [match]
    return matches,matches_by_creation_date
