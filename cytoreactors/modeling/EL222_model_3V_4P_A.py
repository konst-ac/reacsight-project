
# to avoid un-indentifiability we fixed the mRNA prod rate as mrna decay so that ss mrna levels are 1

import numpy as np


def derivs(t, y, model_pars, light_intensity):
    mrna,prefp,fp = y
    # prod rate is a function of current intensity
    prod = light_intensity / 40. * model_pars['deg_m']
    # derivs per se
    dmrna_dt = prod - model_pars['deg_m'] * mrna
    dprefp_dt = model_pars['sigma'] * mrna - model_pars['k_mat'] * prefp - model_pars['deg_fp'] * prefp
    dfp_dt = model_pars['k_mat'] * prefp - model_pars['deg_fp'] * fp
    return np.array([dmrna_dt,dprefp_dt,dfp_dt])

#
default_model_pars = {'deg_fp':0.4, 'deg_m':1.6, 'k_mat':5., 'sigma':2000.}
