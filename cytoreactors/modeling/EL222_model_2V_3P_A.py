
# to avoid un-indentifiability we fixed the mRNA prod rate as mrna decay so that ss mrna levels are 1

import numpy as np


def derivs(t, y, model_pars, light_intensity):
    mrna,fp = y
    # prod rate is a function of current intensity
    prod = light_intensity / 40. * model_pars['deg_m']
    # derivs per se
    dmrna_dt = prod - model_pars['deg_m'] * mrna
    dfp_dt = model_pars['sigma'] * mrna - model_pars['deg_fp'] * fp
    return np.array([dmrna_dt,dfp_dt])


def analytic(model_pars, light_intensity, y0, duration):
    mrna_0,fp_0 = y0
    delta_light = light_intensity / 40.
    expo_deg_m = np.exp(- model_pars['deg_m'] * duration)
    mrna = mrna_0 * expo_deg_m  + delta_light * (1. - expo_deg_m)
    expo_deg_fp = np.exp(- model_pars['deg_fp'] * duration)
    fp = delta_light * model_pars['sigma'] / model_pars['deg_fp']
    fp += model_pars['sigma'] * (delta_light - mrna_0) / (model_pars['deg_m'] - model_pars['deg_fp']) * expo_deg_m
    fp += (fp_0 - delta_light * model_pars['sigma'] / model_pars['deg_fp']) * expo_deg_fp
    fp -= model_pars['sigma'] * (delta_light - mrna_0) / (model_pars['deg_m'] - model_pars['deg_fp']) * expo_deg_fp
    return np.array([mrna,fp])

#
default_model_pars = {'deg_fp':0.41, 'deg_m':1.58, 'sigma':2000.}
num_variables = 2
