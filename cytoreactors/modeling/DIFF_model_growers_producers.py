
import numpy as np

def derivs(t, y, model_pars, light_intensity):
    g,p = y
    # prod rate is a function of current intensity
    diff_rate = light_intensity / 40. * model_pars['k_diff']
    # dil rate as per turbidostat
    dil = (model_pars['mu_g'] * g + model_pars['mu_p'] * p) / (g + p)
    # derivs per se
    dg_dt = model_pars['mu_g'] * g - diff_rate * g - dil * g
    dp_dt = model_pars['mu_p'] * p + diff_rate * g - dil * p
    return np.array([dg_dt,dp_dt])

#
default_model_pars = {'mu_g':0.35, 'mu_p':0., 'k_diff':0.95}
num_variables = 2
