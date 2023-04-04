
import numpy as np


def derivs(t, y, model_pars, light_intensity):
    naive,immune,rec = y
    # prod rate is a function of current intensity
    k_rec = light_intensity / 40. * model_pars['k']
    # dil rate as per turbidostat
    dil =  model_pars['alpha'] * (naive + model_pars['r'] * rec + immune) / (naive + rec + immune)
    # derivs per se
    dn_dt = model_pars['alpha'] * naive - k_rec * naive - dil * naive
    dr_dt = model_pars['alpha'] * model_pars['r'] * rec + k_rec * naive - model_pars['gamma'] * rec - dil * rec
    di_dt = model_pars['alpha'] * immune + model_pars['gamma'] * rec - dil * immune
    return np.array([dn_dt,di_dt,dr_dt])

#
default_model_pars = {'alpha':0.4, 'k':4., 'r':0., 'gamma':0.}
num_variables = 3
