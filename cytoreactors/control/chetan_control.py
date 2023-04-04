from cytoreactors.control.MPC import CytoDataAnalyzer, trigger_new_cyto_data, DutyCycleController
from cytoreactors.design.events import Event
import logging
from cytoreactors.modeling.simulation import simulate_from_led_history
from time import time

data_analyzer = CytoDataAnalyzer(gating_size_threshold=0.2, gating_doublet_threshold=0.5)

def action_MPC_growers_with_reservoir(program, pars, state):
    # extract last cytometer data
    last_tp = state['current_tp']
    data_last_tp = program.cells.query(f'time_s == {last_tp}')
    data_last_sampling_tp = data_last_tp['sampling_time_s'].iloc[0]
    logging.info('T= {}| MPC reactor {} - last measurement sampled at time: {}'.format(time(),program.reactor_id,data_last_sampling_tp))
    # estimate state at the time of sampling (fraction of diff cells, via threshold on mNeonGreen)
    data_deconv_gated = data_analyzer.treat_new_data(data_last_tp)
    # then threshold of 200
    if len(data_deconv_gated) == 0:
        diff_frac = 0
    else:
        diff_frac = sum(data_deconv_gated['mNeonGreen'] > 200.) / len(data_deconv_gated)
    state['estimate_diff_frac'].append((data_last_sampling_tp, diff_frac))
    logging.info('T= {}| MPC reactor {} - estim diff fract at last sampling: {}'.format(time(),program.reactor_id,diff_frac))
    # extrapolate the effect of the light program between time of sampling and now
    controller = pars['controller']
    t0_abs_s = data_last_sampling_tp - 3600*2.5 # IT IS HERE THAT WE ACCOUNT FOR AN OBSERVATION DELAY !
    tend_abs_s = time()
    df_leds = program.data_to_df('LEDs')
    t,y,_,_ = simulate_from_led_history(model=controller.model,
                                        model_pars=controller.model_pars,
                                        y0=[diff_frac],
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

from cytoreactors.modeling import DIFF_model_all_growers_with_reservoir
def create_event_MPC_growers_with_reservoir(target, light_intensity=40):
    state = {'last_change_tp':0., 'current_tp':0., 'estimate_diff_frac':[], 'dc_history':[]}
    controller = DutyCycleController(target=target,
                                     model=DIFF_model_all_growers_with_reservoir,
                                     model_pars=DIFF_model_all_growers_with_reservoir.default_model_pars.copy(),
                                     initial_state=[0.],
                                     intensity=light_intensity)
    pars = {'controller':controller}
    event = Event(trigger=trigger_new_cyto_data,
                  action=action_MPC_growers_with_reservoir,
                  pars=pars,
                  state=state)
    return event
