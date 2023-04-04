
import numpy as np

def analytic(model_pars, light_intensity, y0, duration):
    r0 = y0[0]
    k = light_intensity / 40. * model_pars['k_diff']
    mu = model_pars['mu']
    alp = model_pars['alpha']
    gamma = mu*alp
    r = (r0 - k/(gamma+k)) * np.exp(-(gamma+k)*duration) + k/(gamma+k)
    return np.array([r])

#
default_model_pars = {'mu':0.4, 'k_diff':0.83,'alpha':0.2}
num_variables = 1
