
import numpy as np
import scipy.integrate as integrate

def derivs(t, y, model_pars, light_intensity, is_stim_long):
    g,p,e,d = y
    dr = 0
    u = light_intensity / 40.
    if light_intensity > 0:
        if is_stim_long > 0:
            dr = model_pars['drh']
        else:
            dr = model_pars['dru']
    kappa = (g*model_pars['gg'] + p*model_pars['gp'] + e*model_pars['ge'] - d*model_pars['de']) / (g + p + e + d)
    dgdt = g*(model_pars['gg'] - (model_pars['bdr']+(dr*u))-kappa)
    dpdt = p*(model_pars['gp'] - model_pars['er']-model_pars['dd']-kappa) + g*((dr*u) + model_pars['bdr'])
    dedt = p*model_pars['er'] + e*(model_pars['ge']-kappa)
    dddt = p*model_pars['dd'] - d*(kappa + model_pars['de'])
    return np.array([dgdt,dpdt,dedt,dddt])
    #print(f'g = {g}, p = {p}, e = {e}, d={d} -- dr = {dr}, kappa = {kappa}, derivs = {}')
#
default_model_pars = {'gg':0.4,
                      'gp':0.04,
                      'ge':0.4,
                      'bdr':0.0919,
                      'dru':1.05,
                      'drh':2.56,
                      'er':1.02e-7,
                      'dd':0.187,
                      'de':0.766}
num_variables = 4

def simulate(model, model_pars, light_profile, y0, t0=0, method='RK45', n_evals=2):
    # light_profile should be a list of tuple (intensity,duration_in_hr)
    # we assume the model time unit is 1 hour
    # y0 can be a list or a 1D np.array, length should match number of vars in the model
    ys = [] # storing full solver output of model vars
    ts = [] # storing full solver output of time
    rec_alive_frac_at_edges = [(y0[1]+y0[2])/(1-y0[-1])] # storing rec ALIVE frac in between change of light
    t_at_edges = [t0]
    # do one integration call per interval of light
    for intensity,duration in light_profile:
        #print(f'I = {intensity} for duration = {duration}')
        if duration > 0:
            is_stim_long = False
            if intensity > 0 and duration > 0.495:
                is_stim_long = True
            ode_result = integrate.solve_ivp(lambda t,y: model.derivs(t,y,model_pars,intensity,is_stim_long), # the RHS for the ODEs
                                         (t0,t0+duration), # time interval
                                         y0, # initial condition
                                         method=method,
                                         t_eval=np.linspace(t0,t0+duration,n_evals),
                                         dense_output=False,
                                         rtol=1e-6, atol=1e-6)
            ys.append(ode_result.y)
            ts.append(ode_result.t)
            y0 = ode_result.y[:,-1]
            rec_alive_frac_at_edges.append((y0[1]+y0[2])/(1-y0[-1]))
            t_at_edges.append(ode_result.t[-1])
            t0 += duration
    return np.concatenate(ts), np.hstack(ys), np.array(rec_alive_frac_at_edges), np.array(t_at_edges)
