from  scipy.optimize import minimize_scalar, minimize
from cytoreactors.design.events import Event
from cytoreactors.modeling.simulation import simulate, simulate_analytic, simulate_from_led_history
from guava2data import gating
import numpy as np
from time import time
import logging

class DutyCycleController:
    def __init__(self, target, model, model_pars, initial_state, dc_period_hrs=0.5, n_cycles_horizon=10, intensity=40):
        self.target = target
        self.model = model
        if hasattr(self.model, 'analytic'):
            self.sim_fun = simulate_analytic
        elif hasattr(self.model, 'simulate'):
            self.sim_fun = model.simulate
        else:
            self.sim_fun = simulate
        self.model_pars = model_pars
        self.initial_state = initial_state
        self.current_state = initial_state
        self.dc_period_hrs = dc_period_hrs
        self.n_cycles_horizon = n_cycles_horizon
        self.intensity = intensity
    ## utils
    def dcs_to_light_profile(self, dcs):
        light_profile = []
        for dc in dcs:
            light_profile.append((self.intensity, dc*self.dc_period_hrs))
            light_profile.append((0., (1-dc)*self.dc_period_hrs))
        return light_profile
    ## controller optimization
    def cost_dc_optim(self, dcs):
        light_profile = self.dcs_to_light_profile(dcs)
        _,_,fp_at_edges,_ = self.sim_fun(model=self.model, model_pars=self.model_pars, light_profile=light_profile, y0=self.current_state)
        return np.square(fp_at_edges[1:-1:2]-self.target).sum()
    def optimize(self):
        res = minimize(fun=self.cost_dc_optim,
                        x0=[0.5]*self.n_cycles_horizon,
                        args=(),
                        method='L-BFGS-B',
                        bounds=[(0.,1.)]*self.n_cycles_horizon)
        return res.x
    def apply_dcs(self, dcs, t0=0., n_evals=2):
        light_profile = self.dcs_to_light_profile(dcs)
        t,y,_ = self.sim_fun(model=self.model, model_pars=self.model_pars, light_profile=light_profile, y0=self.current_state, t0=t0, n_evals=n_evals)
        self.current_state = y[:,-1]
        return t,y


## to use in event logic
def trigger_new_cyto_data(program, pars, state):
    if program.cells is None:
        return False
    max_tp = max([tp for tp,_ in program.cells.groupby('time_s')])
    state['current_tp'] = max_tp
    if max_tp > state['last_change_tp']:
        return True
    return False

def action_diff_MPC(program, pars, state):
    # extract last cytometer data
    last_tp = state['current_tp']
    data_last_tp = program.cells.query(f'time_s == {last_tp}')
    data_last_sampling_tp = data_last_tp['sampling_time_s'].iloc[0]
    logging.info('T= {}| MPC - last measurement sampled at time: {}'.format(time(),data_last_sampling_tp))
    # estimate state at the time of sampling (fraction of diff cells, via threshold on ORG-G ?)
    # first gate
    data_gated = gating.compute_ks_FSC_SSC_gating_metric(data_last_tp)
    data_gated = gating.compute_doublet_metric(data_gated)
    data_gated = data_gated[data_gated['doublet-metric'] < 0.5]
    data_gated = data_gated[data_gated['gating-metric'] > 0.1]
    # then threshold of 500
    if len(data_gated) == 0:
        diff_frac = 0
    else:
        diff_frac = sum(data_gated['ORG-G-HLin'] > 1000.) / len(data_gated)
    state['estimate_diff_frac'].append((data_last_sampling_tp, diff_frac))
    logging.info('T= {}| MPC - estim diff fract at last sampling: {}'.format(time(),diff_frac))
    # extrapolate the effect of the light program between time of sampling and now
    controller = pars['controller']
    t0_abs_s = data_last_sampling_tp - 3600*2.5 # IT IS HERE THAT WE ACCOUNT FOR AN OBSERVATION DELAY !
    tend_abs_s = time()
    df_leds = program.data_to_df('LEDs')
    t,y,_,_ = simulate_from_led_history(model=controller.model,
                                        model_pars=controller.model_pars,
                                        y0=[1-diff_frac, diff_frac],
                                        df_leds=df_leds,
                                        t0_abs_s=t0_abs_s,
                                        tend_abs_s=tend_abs_s)
    controller.current_state = y.transpose()[-1]
    logging.info('T= {}| MPC - current state estim: {}'.format(time(),controller.current_state))
    # finally can do the proper search
    dcs = controller.optimize()
    # we store and apply it
    state['dc_history'].append((time(),dcs))
    program.set_LED(0) # will also remove all planned changes
    period_s = 3600. * controller.dc_period_hrs
    for i,dc in enumerate(dcs): # normally will be used only for two cycles only
        program.schedule_LED_change(controller.intensity, i*period_s)
        program.schedule_LED_change(0, i*period_s+dc*period_s)
    state['last_change_tp'] = state['current_tp']

def action_fluo_MPC_simple_state_estimation(program, pars, state):
    last_tp = state['current_tp']
    data_last_tp = program.cells.query(f'time_s == {last_tp}')
    last_measurement = data_last_tp['GRN-B-HLin'].median()
    data_last_sampling_tp = data_last_tp['sampling_time_s'].iloc[0]
    logging.info('T= {}| MPC - last measurement: {} sampled at time: {}'.format(time(),last_measurement,data_last_sampling_tp))
    # extrapolate the effect of the light program between last sampling and now
    # but for this we need an estimate of non-measured model variables at the moment of the last sampling ? what to do ?
    # maybe simply simulate the whole history ? let's do that for now
    ### between beginning of exp and last sampling time
    t0_abs_s = program.data_to_df('ODs')['time_s'].iloc[0]
    tend_abs_s = data_last_sampling_tp
    df_leds = program.data_to_df('LEDs')
    controller = pars['controller']
    t,y,_,_ = simulate_from_led_history(model=controller.model,
                                        model_pars=controller.model_pars,
                                        y0=self.initial_state,
                                        df_leds=df_leds,
                                        t0_abs_s=t0_abs_s,
                                        tend_abs_s=tend_abs_s)
    estim_y_last_sampling = y.transpose()[-1]
    logging.info('T= {}| MPC - estim y last sampling before setting measurement: {}'.format(time(),estim_y_last_sampling))
    # now simulate btw last_sampling and now, using measurement in the estimate
    t0_abs_s = data_last_sampling_tp
    tend_abs_s = time()
    estim_y_last_sampling[-1] = last_measurement # use real measure for measured variable
    t,y,_,_ = simulate_from_led_history(model=self.model, model_pars=self.model_pars, y0=estim_y_last_sampling, df_leds=df_leds,
                                        t0_abs_s=t0_abs_s, tend_abs_s=tend_abs_s)
    self.current_state = y.transpose()[-1]
    logging.info('T= {}| MPC - current state estim: {}'.format(time(),self.current_state))
    # finally can do the proper search
    dcs = self.optimize()
    # we store and apply it
    state['dc_history'].append((time(),dcs))
    program.set_LED(0) # will also remove all planned changes
    period_s = 3600. * self.dc_period_hrs
    for i,dc in enumerate(dcs): # normally will be used only for two cycles only
        program.schedule_LED_change(controller.intensity, i*period_s)
        program.schedule_LED_change(0, i*period_s+dc*period_s)
    state['last_change_tp'] = state['current_tp']

class IntensityController:
    def __init__(self, target, model, model_pars, initial_state, period_hrs=0.5, n_cycles_horizon=5, intensity_max=40.):
        self.target = target
        self.model = model
        self.model_pars = model_pars
        self.initial_state = initial_state
        self.current_state = initial_state
        self.period_hrs = period_hrs
        self.n_cycles_horizon = n_cycles_horizon
        self.intensity_max = intensity_max
    ## utils
    def intensities_to_light_profile(self, intensities):
        return [(I,self.period_hrs) for I in intensities]
    ## controller optimization
    def cost_optim(self, intensities):
        light_profile = self.intensities_to_light_profile(intensities)
        _,y,fp_at_edges = simulate(model=self.model, model_pars=self.model_pars, light_profile=light_profile, y0=self.current_state, n_evals=21)
        return np.square(y[-1,:]-self.target).sum()
    def optimize(self):
        res = minimize(fun=self.cost_optim,
                        x0=[0.*self.intensity_max]*self.n_cycles_horizon,
                        args=(),
                        method='L-BFGS-B',
                        bounds=[(0.,self.intensity_max)]*self.n_cycles_horizon)
        return res.x
    def apply_intensities(self, intensities, t0=0., n_evals=2):
        light_profile = self.intensities_to_light_profile(intensities)
        t,y,_ = simulate(model=self.model, model_pars=self.model_pars, light_profile=light_profile, y0=self.current_state, t0=t0, n_evals=n_evals)
        self.current_state = y[:,-1]
        return t,y


# utilities for data analysis
from guava2data import gating, deconvolution, analysis
from cytoreactors import __path__ as package_path_list
package_path = package_path_list[0]
import pandas as pd

class CytoDataAnalyzer:
    def __init__(self,
                 AF_ref_csv_path=f'{package_path}/calibration/reference-guava-AF-strain-IB20056-media-SC-LoFlo.csv',
                 gating_size_threshold=0.8,
                 gating_doublet_threshold=0.5,
                 FPs=['mCerulean', 'mNeonGreen', 'mVenus', 'mScarletI']):
        self.gating_size_threshold = gating_size_threshold
        self.gating_doublet_threshold = gating_doublet_threshold
        self.FPs = FPs
        AF_ref = pd.read_csv(AF_ref_csv_path)
        AF_gated = analysis.filter_data(AF_ref, self.gating_size_threshold, self.gating_doublet_threshold)
        self.AF_medians = AF_gated.median()
    def treat_new_data(self,data):
        data_gated = analysis.filter_data(data, self.gating_size_threshold, self.gating_doublet_threshold)
        data_deconv = deconvolution.infer_FP_amounts(data_gated, self.AF_medians, self.FPs)
        return data_deconv
