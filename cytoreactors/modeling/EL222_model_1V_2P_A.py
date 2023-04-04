
import numpy as np

def derivs(t, y, model_pars, light_intensity):
    fp = y
    # prod rate is a function of current intensity
    prod = light_intensity / 40. * model_pars['sigma']
    # derivs per se
    dfp_dt = prod - model_pars['deg_fp'] * fp
    return np.array([dfp_dt])

#
default_model_pars = {'deg_fp':0.3, 'sigma':1300.}
