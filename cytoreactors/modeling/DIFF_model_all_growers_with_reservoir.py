
import numpy as np

def analytic(model_pars, light_intensity, y0, duration):
    r0 = y0[0]
    k = light_intensity / 40. * model_pars['k_diff']
    mu = model_pars['mu']
    r = (r0 - k/(mu+k)) * np.exp(-(mu+k)*duration) + k/(mu+k)
    return np.array([r])

#
default_model_pars = {'mu':0.4, 'k_diff':4.}
num_variables = 1
