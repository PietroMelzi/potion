from lqg1Dscalable.abstraction.deterministic_abstraction import DeterministicAbstraction
import lqg1Dscalable.abstraction.compute_atf.abstract_tf.uniform_state_distribution as uni_dist


class LipschitzFds(DeterministicAbstraction):

    def __init__(self, lipschitz, gamma, sink, intervals=None):
        super().__init__(gamma, sink, intervals)
        self.LIPSCHITZ_CONST_F = lipschitz

    def calculate_single_atf(self, cont, act):
        new_state_bounds = []
        for action in cont.keys():
            state_distance = abs(cont[act]['state'] - cont[action]['state'])
            # I obtain the min & max new state I would get by performing action act in every state sampled.
            min_val = cont[act]['new_state'] - self.LIPSCHITZ_CONST_F * state_distance
            max_val = cont[act]['new_state'] + self.LIPSCHITZ_CONST_F * state_distance
            new_state_bounds.append([min_val, max_val])

        return uni_dist.abstract_tf(self.intervals, new_state_bounds, self.sink)
        # return sample_dist.abstract_tf(self.intervals, new_state_bounds, self.sink)