
class Event:
    def __init__(self, trigger, action, pars=None, state=None):
        self.trigger = trigger
        self.action = action
        if pars is None:
            self.pars = {}
        else:
            self.pars = pars
        if state is None:
            self.state = {}
        else:
            self.state = state
    def check_and_apply(self, program):
        if self.trigger(program=program, pars=self.pars, state=self.state):
            self.action(program=program, pars=self.pars, state=self.state)
