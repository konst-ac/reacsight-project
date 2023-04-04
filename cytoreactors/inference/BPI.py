import numpy as np
from cytoreactors.modeling.simulation import simulate_analytic

class Particles:
    def __init__(self, n_particles, model, init_param_uncertainty_delta_log=0):
        self.n_particles = n_particles
        self.model = model
        self.n_state_vars = self.model.num_variables
        self.param_names = list(self.model.default_model_pars.keys())
        self.params = {}
        for param_name in self.param_names:
            self.params[param_name] = self.model.default_model_pars[param_name] * np.ones(self.n_particles) * np.exp(np.random.normal(0,init_param_uncertainty_delta_log,self.n_particles))
        self.states = np.zeros((self.n_particles,self.n_state_vars))
    def get_particle_pars(self, ip):
        return {pname:pvals[ip] for pname,pvals in self.params.items()}
    def advance(self, light_profile):
        for ip in range(self.n_particles):
            pars = self.get_particle_pars(ip)
            _,y,_,_ = simulate_analytic(self.model, pars, light_profile, self.states[ip])
            self.states[ip] = y[:,-1]
    def diffuse(self, jump_size=0.1):
        for p in self.params:
            delta_log = np.random.normal(scale=jump_size, size=self.params[p].shape)
            self.params[p] *= np.exp(delta_log)
    def treat_new_measurement(self, fp_measurement, sigma_fp_measurement):
        # compute likelihood of particles
        lls = np.exp(-(fp_measurement - self.states[:,-1])**2 / 2. / sigma_fp_measurement**2)
        # draw particles according to likelihoods
        lls /= lls.sum()
        lls_cum = lls.cumsum()
        lls_cum = np.repeat(lls_cum.reshape(len(lls_cum),1),len(lls_cum),axis=1)
        us = np.repeat(np.random.rand(len(lls)).reshape(1,len(lls)),len(lls),axis=0)
        ip_drawn = np.argmax(us < lls_cum, axis=0)
        # update particles
        self.states = self.states[ip_drawn]
        for p_name,p_vals in self.params.items():
            self.params[p_name] = p_vals[ip_drawn]
    def forecast(self, light_profile): # here we don't change the particle state ! It is for MPC
        forecast_states = np.empty((self.n_particles,self.n_state_vars))
        for ip in range(self.n_particles):
            pars = self.get_particle_pars(ip)
            _,y,_,_ = simulate_analytic(self.model, pars, light_profile, self.states[ip])
            forecast_states[ip] = y[:,-1]
        return forecast_states
    def forecast_trajectories(self, light_profile, is_measurement, n_particles=None):
        if n_particles is None:
            n_particles = self.n_particles
        n_measurements = sum(is_measurement)
        forecast_trajs = np.empty((n_particles,n_measurements))
        for ip in range(n_particles):
            pars = self.get_particle_pars(ip)
            _,_,fp_at_edges,t_at_edges = simulate_analytic(self.model, pars, light_profile, self.states[ip])
            forecast_trajs[ip] = fp_at_edges[is_measurement]
        return forecast_trajs
