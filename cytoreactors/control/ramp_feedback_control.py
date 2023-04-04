from cytoreactors.design.events import Event
import time

def time_ramp_trigger(program, pars, state):
    return time.time() - state['last_change_time'] > 3*3600

def time_and_growth_rate_trigger(program, pars, state):
    if time.time() - state['last_change_time'] < 3*3600:
        return False
    return program.growth_rates['growth_rate_per_hr'].iloc[-1] > 0.3

def last_UPR_trigger(program, pars, state):
    if program.cells is None:
        return False
    last_tp = max([tp for tp,_ in program.cells.groupby('time_s')])
    if last_tp > state['last_change_time']:
        data_last_tp = program.cells.query(f'time_s == {last_tp}')
        upr_value = (data_last_tp['ORG-G-HLin']/data_last_tp['FSC-HLin']).median()
        return upr_value < pars['threshold']

def last_internal_FP_trigger(program, pars, state):
    if program.cells is None:
        return False
    last_tp = max([tp for tp,_ in program.cells.groupby('time_s')])
    if last_tp > state['last_change_time']:
        data_last_tp = program.cells.query(f'time_s == {last_tp}')
        internal_value = (data_last_tp['GRN-B-HLin']/data_last_tp['FSC-HLin']).median()
        return internal_value < pars['threshold']

def dc_ramp_action(program, pars, state):
    state['last_change_time'] = time.time()
    state['current_dc'] += 0.1
    if state['current_dc'] > 1:
        state['current_dc'] = 1
    period_s = 3600. * 0.5
    program.start_LED_duty_cycle(40, period_s, state['current_dc'], 200)