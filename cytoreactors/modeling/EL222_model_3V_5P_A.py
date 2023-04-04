
# to avoid un-indentifiability we fixed the mRNA prod rate as mrna decay + dil so that ss mrna levels are 1

import numpy as np


def derivs(t, y, model_pars, light_intensity):
    mrna,prefp,fp = y
    # prod rate is a function of current intensity
    prod = light_intensity / 40. * (model_pars['deg_m'] + model_pars['dil_rate'])
    # derivs per se
    dmrna_dt = prod - model_pars['deg_m'] * mrna - model_pars['dil_rate'] * mrna
    dprefp_dt = model_pars['sigma'] * mrna - model_pars['k_mat'] * prefp - model_pars['dil_rate'] * prefp
    dfp_dt = model_pars['k_mat'] * prefp - model_pars['deg_fp'] * fp - model_pars['dil_rate'] * fp
    return np.array([dmrna_dt,dprefp_dt,dfp_dt])

#
default_model_pars = {'dil_rate':0.4, 'deg_fp':0.05, 'deg_m':1.2, 'k_mat':5., 'sigma':2000.}
