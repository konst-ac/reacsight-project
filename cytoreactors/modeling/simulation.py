### code for simulating models
### separate for model to impose single interface btw model and simulation and limit code duplications

import scipy.integrate as integrate
import numpy as np

def simulate_analytic(model, model_pars, light_profile, y0, t0=0, n_evals=2):
    y = y0
    ys = [y]
    ts = [t0]
    fp_at_edges = [y0[-1]]
    t_at_edges = [t0]
    for intensity,duration in light_profile:
        if duration > 0:
            delta_t = duration / (n_evals - 1.)
            for n in range(n_evals - 1):
                y = model.analytic(model_pars, intensity, y, delta_t)
                ys.append(y)
                ts.append(ts[-1]+delta_t)
        fp_at_edges.append(y[-1])
        t_at_edges.append(ts[-1])
    y = np.vstack(ys).T
    t = np.array(ts)
    return t, y, np.array(fp_at_edges), np.array(t_at_edges)

def simulate(model, model_pars, light_profile, y0, t0=0, method='RK45', n_evals=2):
    # light_profile should be a list of tuple (intensity,duration_in_hr)
    # we assume the model time unit is 1 hour
    # y0 can be a list or a 1D np.array, length should match number of vars in the model
    ys = [] # storing full solver output of model vars
    ts = [] # storing full solver output of time
    fp_at_edges = [y0[-1]] # storing only model last variable, assumed to be the fp observed, in between change of light
    t_at_edges = [t0]
    # do one integration call per interval of light
    for intensity,duration in light_profile:
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
            fp_at_edges.append(y0[-1])
            t_at_edges.append(ode_result.t[-1])
            t0 += duration
    return np.concatenate(ts), np.hstack(ys), np.array(fp_at_edges), np.array(t_at_edges)

# interface to bioreactor df leds (where time is in seconds !)
def simulate_from_led_history(model, model_pars, df_leds, y0, t0_abs_s, tend_abs_s, intensity_at_t0=0., method='RK45', n_evals=2):
    # do I need to extract intensity at t0 from df_leds ?
    if not df_leds.empty and t0_abs_s > df_leds['time_s'].iloc[0]:
        intensity_at_t0 = df_leds.query(f'time_s <= {t0_abs_s}')['intensity'].iloc[-1]
    # select relevant led data
    df_leds = df_leds.query(f'time_s < {tend_abs_s}').query(f'time_s >= {t0_abs_s}').copy()
    # build light profile
    light_profile = []
    if df_leds.empty:
        light_profile.append((intensity_at_t0, (tend_abs_s-t0_abs_s)/3600.))
    else:
        # period before first led change
        light_profile.append((intensity_at_t0, (df_leds['time_s'].iloc[0] - t0_abs_s)/3600.))
        # period btw light changes
        for i in range(1,len(df_leds)):
            dt_hrs = (df_leds['time_s'].iloc[i]-df_leds['time_s'].iloc[i-1])/3600.
            light_profile.append((df_leds['intensity'].iloc[i-1], dt_hrs))
        # period after last_change
        dt_hrs = (tend_abs_s-df_leds['time_s'].iloc[-1])/3600.
        light_profile.append((df_leds['intensity'].iloc[-1], dt_hrs))
    # simulate
    if hasattr(model, 'analytic'):
        ts,ys,fp_at_edges,_ = simulate_analytic(model, model_pars, light_profile, y0, n_evals=n_evals)
    elif hasattr(model, 'simulate'):
        ts,ys,fp_at_edges,_ = model.simulate(model, model_pars, light_profile, y0, method=method, n_evals=n_evals)
    else:
        ts,ys,fp_at_edges,_ = simulate(model, model_pars, light_profile, y0, method=method, n_evals=n_evals)
    return ts,ys,fp_at_edges,light_profile # careful, ts in hours relative to t0 abs s

def light_profile_to_traj(profile):
    t = 0
    ts = []
    intensities = []
    for intensity,duration in profile:
        if duration > 0:
            ts += [t,t+duration]
            intensities += [intensity,intensity]
            t += duration
    return np.array(ts),np.array(intensities)

def light_profile_to_t_change(profile):
    ts = [0]
    for _,duration in profile:
        ts.append(ts[-1]+duration)
    return np.array(ts)

def integrate_timepoints_in_light_profile(light_profile, t_measurements):
    assert(sum([d for _,d in light_profile]) >= t_measurements[-1])
    light_profile_and_measurements = [(I,d,False) for I,d in light_profile]
    for t_measurement in t_measurements:
        i = 0
        t = 0
        while t + light_profile_and_measurements[i][1] < t_measurement:
            t += light_profile_and_measurements[i][1]
            i += 1
        lpm_before = light_profile_and_measurements[:i] + [(light_profile_and_measurements[i][0],t_measurement-t,True)]
        lpm_after = []
        if light_profile_and_measurements[i][1]-t_measurement+t>0:
            lpm_after = [(light_profile_and_measurements[i][0],light_profile_and_measurements[i][1]-t_measurement+t,False)]
        lpm_after += light_profile_and_measurements[i+1:]
        light_profile_and_measurements = lpm_before + lpm_after
    lp = [(I,d) for I,d,_ in light_profile_and_measurements]
    is_m = [False] + [b for _,_,b in light_profile_and_measurements]
    return lp,np.array(is_m)
