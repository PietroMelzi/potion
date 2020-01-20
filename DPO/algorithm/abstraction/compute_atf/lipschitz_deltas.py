from DPO.algorithm.abstraction.lipschitz_abstraction import LipschitzAbstraction
import DPO.algorithm.abstraction.compute_atf.abstract_tf.sample_distribution as sample_dist
import DPO.algorithm.abstraction.compute_atf.abstract_tf.bounded_atf as bounded_atf
import DPO.helper as helper
import numpy as np
import logging
# import DPO.visualizer.bounds_visualizer as bvis
import gym
import potion.envs


class LipschitzDeltaS(LipschitzAbstraction):

    def __init__(self, gamma, sink, intervals=None, ls=None, la=None, Q=None, R=None, maxa_env=1):
        super().__init__(gamma, sink, intervals, Q, R, maxa_env)

    # ds0 is True when the hypothesis of deltaS = 0 is valid.
    # It means that taking the same action in different states will produce the same delta s (deltas = s' - s).
    def calculate_single_atf(self, mcrst, key, ds0, mins_env, maxs_env, maxa_env, std=0):

        cont = self.container[mcrst]
        new_states = []
        delta_s = cont[key]['new_state'] - cont[key]['state']

        for k, v in cont.items():

            ns = cont[k]['state'] + delta_s
            ns = np.clip(ns, mins_env, maxs_env)
            new_states.append(ns)

        return sample_dist.abstract_tf(self.intervals, new_states, self.sink)
