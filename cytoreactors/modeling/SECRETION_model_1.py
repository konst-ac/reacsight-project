
import numpy as np

def derivs(t, y, model_pars, light_intensity):
    Pin,R = y
    prod_Pin = light_intensity * model_pars['k_prod']
    degrad_Pin = Pin*R*model_pars['R_action_rate']
    n,c = model_pars['prod_R_hill_exp'],model_pars['prod_R_hill_conc']
    prod_R = model_pars['prod_R_basal'] + (model_pars['prod_R_max']-model_pars['prod_R_basal']) * Pin**n / (Pin**n + c**n)
    n,c = model_pars['growth_defect_hill_exp'],model_pars['growth_defect_hill_conc']
    mu = model_pars['mu_max'] * c**n / (Pin**n + c**n)
    dPin_dt = prod_Pin - degrad_Pin - mu * Pin
    dR_dt = prod_R - mu * R
    return np.array([dPin_dt,dR_dt])

default_model_pars = {'mu_max':0.4, 'k_prod':1,
                      'growth_defect_hill_exp':2, 'growth_defect_hill_conc':10,
                      'prod_R_max':1, 'prod_R_hill_exp':2, 'prod_R_hill_conc':20, 'prod_R_basal':0.1,
                      'R_action_rate':1}
num_variables = 2
