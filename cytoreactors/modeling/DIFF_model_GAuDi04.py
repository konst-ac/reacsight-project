
import numpy as np
import scipy.integrate as integrate

def derivs(t, y, model_pars, light_intensity):
    g,p = y
    u = light_intensity / 40.
    kappa = (g*model_pars['gg'] + p*model_pars['gp']) / (g + p )
    dgdt = g*(model_pars['gg'] - (model_pars['dr']*u) - kappa)
    dpdt = p*(model_pars['gp']  - kappa) + g*(model_pars['dr']*u )
    return np.array([dgdt,dpdt])

default_model_pars = {'gg':3.5087e-01,
                      'gp':3.171321e-01,
                      'dr':1.4811,
                      }
num_variables = 2

def simulate(model, model_pars, light_profile, y0, t0=0, method='RK45', n_evals=2):
    # light_profile should be a list of tuple (intensity,duration_in_hr)
    # we assume the model time unit is 1 hour
    # y0 can be a list or a 1D np.array, length should match number of vars in the model
    ys = [] # storing full solver output of model vars
    ts = [] # storing full solver output of time
    rec_total_frac_at_edges = [y0[1]] # storing rec  fraction, in between change of light
    t_at_edges = [t0]
    # do one integration call per interval of light
    for intensity,duration in light_profile:
        #print(f'I = {intensity} for duration = {duration}')
        if duration > 0:
            ode_result = integrate.solve_ivp(lambda t,y: model.derivs(t,y,model_pars,intensity), # the RHS for the ODEs
                                         (t0,t0+duration), # time interval
                                         y0, # initial condition
                                         method=method,
                                         t_eval=np.linspace(t0,t0+duration,n_evals),
                                         dense_output=False,
                                         rtol=1e-6, atol=1e-6)
            ys.append(ode_result.y)
            ts.append(ode_result.t)
            y0 = ode_result.y[:,-1]
            rec_total_frac_at_edges.append(y0[1])
            t_at_edges.append(ode_result.t[-1])
            t0 += duration
    return np.concatenate(ts), np.hstack(ys), np.array(rec_total_frac_at_edges), np.array(t_at_edges)
