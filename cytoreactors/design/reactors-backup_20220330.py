
class Reactor:
    def __init__(self, reactor_id, program = None):
        self.reactor_id = reactor_id
        self.reactor_set_id = (reactor_id-1) // 4 + 1
        self.bubbling_set_id = 'B' + str(self.reactor_set_id)
        self.out_valve_id = 'F' + str(reactor_id)
        self.pump_in_slot_id = 'L' + str(reactor_id)
        self.pump_out_slot_id = 'H' + str(reactor_id)
        if reactor_id < 9:
            self.sampling_row = {1:'A', 2:'B', 3:'C', 4:'D', 5:'E', 6:'F', 7:'G', 8:'H'}[self.reactor_id]
            self.guava_col = '12' # for ot2, it is col 1
            self.guava_row = {1:'H', 2:'G', 3:'F', 4:'E', 5:'D', 6:'C', 7:'B', 8:'A'}[self.reactor_id]
        else:
            # warning not possible simultaneous
            self.sampling_row = {1:'A', 2:'B', 3:'C', 4:'D', 5:'E', 6:'F', 7:'G', 8:'H'}[self.reactor_id-8]
            self.guava_col = '12' # for ot2, it is col 1
            self.guava_row = {1:'H', 2:'G', 3:'F', 4:'E', 5:'D', 6:'C', 7:'B', 8:'A'}[self.reactor_id-8]
    def __str__(self):
        return 'reactor %i (set %i)' % (self.reactor_id, self.reactor_set_id)

reactors = {id:Reactor(id) for id in range(1,17)}
