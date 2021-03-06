import gym
import potion.envs
import numpy as np
from DPO.algorithm.abstraction.compute_atf.lipschitz_deltas import LipschitzDeltaS
from DPO.algorithm.abstraction.maxlikelihood_abstraction_parallel import MaxLikelihoodAbstraction
from DPO.algorithm.updater_abstract.updater import AbsUpdater
from DPO.algorithm.updater_abstract.bounded_mdp.IVI import IVI
from DPO.algorithm.updater_deterministic.updater import Updater
from DPO.visualizer.lqg1d_visualizer import Lqg1dVisualizer
import DPO.helper as helper
from DPO.helper import Helper
import logging
import csv
from tensorboardX import SummaryWriter


problem = 'lqg1d'
SINK = False
INIT_DETERMINISTIC_PARAM = -0.7
A = 1
B = 1
GAMMA = 0.9

# ds0 = when we consider the problem lipschitz 0 wrt deltas hypothesis (bounded by a distance among states).
# Set ds0 = 0 to use the standard algorithm that computes bounds related to both space and action distances.
ds0 = 0

LIPSCHITZ_CONST_STATE = A
LIPSCHITZ_CONST_ACTION = B
LIPSCHITZ_STOCH_ATF = B

N_ITERATION = 1000
N_EPISODES = 5000
N_STEPS = 20

# INTERVALS = [[-2, -1.8], [-1.8, -1.6], [-1.6, -1.4], [-1.4, -1.2], [-1.2, -1], [-1, -0.8], [-0.8, -0.6], [-0.6, -0.4],
#              [-0.4, -0.2], [-0.2, -0.1], [-0.1, -0.025], [-0.025, 0.025], [0.025, 0.1], [0.1, 0.2], [0.2, 0.4],
#              [0.4, 0.6], [0.6, 0.8], [0.8, 1], [1, 1.2], [1.2, 1.4], [1.4, 1.6], [1.6, 1.8], [1.8, 2]]

# actually used (!)
# INTERVALS = [[-2, -1.6], [-1.6, -1.2], [-1.2, -0.8], [-0.8, -0.5], [-0.5, -0.3], [-0.3, -0.1], [-0.1, 0.1],
#              [0.1, 0.3], [0.3, 0.5], [0.5, 0.8], [0.8, 1.2], [1.2, 1.6], [1.6, 2]]

STOCH = 1
ENV_NOISE = 0.1 if STOCH else 0.
UPD_LAM = 0.005  # Regularization parameter in the policy re-projection.
STOCH_L_MULTIPLIER = 5  # Increase the L constant in stochastic environments.

N_MCRST_DYN = 23 if STOCH else 13
MIN_SPACE_VAL = -2
MAX_SPACE_VAL = 2


def deterministic_action(det_par, state):
    return det_par * state


def sampling_from_det_pol(env, n_episodes, n_steps, det_par):
    samples_list = []
    for i in range(0, n_episodes):
        env.reset()
        single_sample = []
        for j in range(0, n_steps):
            state = env.get_state()
            action = deterministic_action(det_par, state)
            new_state, r, _, _ = env.step(action)
            single_sample.append([state[0], action[0], r, new_state[0]])
        samples_list.append(single_sample)
    return samples_list


def sampling_abstract_optimal_pol(abs_opt_policy, det_samples, param, interv, INTERVALS):
    fictitious_samples = []
    for sam in det_samples:
        single_sample = []
        for s in sam:
            prev_action = deterministic_action(param, s[0])
            if interv is not None:
                mcrst = helper.get_mcrst(s[0], interv, SINK)
            else:
                mcrst = helper.get_mcrst(s[0], INTERVALS, SINK)
            if prev_action in abs_opt_policy[mcrst]:
                single_sample.append([s[0], prev_action])
            else:
                index = np.argmin([abs(act - prev_action) for act in abs_opt_policy[mcrst]])
                single_sample.append([s[0], abs_opt_policy[mcrst][index]])
        fictitious_samples.append(single_sample)
    return fictitious_samples


def estimate_performance_abstract_policy(env, n_episodes, n_steps, abstract_policy, init_states, interv, INTERVALS):
    acc = 0
    for i in range(0, n_episodes):
        env.reset(init_states[i])
        g = 1
        for j in range(0, n_steps):
            state = env.get_state()
            if interv is not None:
                action = abstract_policy[helper.get_mcrst(state, interv, SINK)][0]
            else:
                action = abstract_policy[helper.get_mcrst(state, INTERVALS, SINK)][0]
            new_state, r, _, _ = env.step(action)
            acc += g * r
            g *= GAMMA
    return acc / n_episodes


def main(seed=None):

    help = Helper(seed)

    # load and configure the environment.
    env = gym.make('LQG1D-v0')
    env.sigma_noise = ENV_NOISE
    env.A = np.array([A]).reshape((1, 1))
    env.B = np.array([B]).reshape((1, 1))
    env.gamma = GAMMA
    env.seed(help.getSeed())

    INTERVALS = helper.get_constant_intervals(MIN_SPACE_VAL, MAX_SPACE_VAL, N_MCRST_DYN)
    print("INTERVALS: {}\n{}\n".format(N_MCRST_DYN, INTERVALS))

    # calculate the optimal values of the problem.
    opt_par4vis = round(env.computeOptimalK()[0][0], 3)
    det_param = INIT_DETERMINISTIC_PARAM
    optJ4vis = round(env.computeJ(env.computeOptimalK(), 0, N_EPISODES), 3)
    # logging.basicConfig(level=logging.DEBUG, filename='../test.log', filemode='w', format='%(message)s')

    filename = "../csv/lqg1d/DPO/data{}.csv".format(help.getSeed())
    data_file = open(filename, mode='w')
    file_writer = csv.writer(data_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    # instantiate the components of the algorithm.
    # abstraction = LqgFKnown(A, B, GAMMA, SINK, INTERVALS)
    abstraction = LipschitzDeltaS(GAMMA, SINK, INTERVALS, A, B) if not STOCH else \
        MaxLikelihoodAbstraction(GAMMA, SINK, INTERVALS, B * STOCH_L_MULTIPLIER)

    abs_updater = None
    if not STOCH:
        abs_updater = AbsUpdater(GAMMA, SINK, INTERVALS) if ds0 else IVI(GAMMA, SINK, True, INTERVALS)
    else:
        abs_updater = AbsUpdater(GAMMA, SINK, INTERVALS)
    det_upd = Updater(help.getSeed(), UPD_LAM)

    title = "A={}, B={}, Opt par={}, Opt J={}, Noise std dev={}".format(A, B, opt_par4vis, optJ4vis, ENV_NOISE)
    key = "{}_{}_{}_{}_{}".format(A, B, ENV_NOISE, det_param, help.getSeed())
    key = key.replace('.', ',')
    key = key + ".jpg"
    initJ = env.computeJ(det_param, 0, N_EPISODES)
    visualizer = Lqg1dVisualizer(title, key, det_param, opt_par4vis, initJ, optJ4vis)
    visualizer.clean_panels()

    # PLOTTER INFO
    stats = {}
    stats['param'] = []
    stats['j'] = []
    stats['sampleJ'] = []
    stats['abstractJ'] = []
    stats['param'].append(det_param)
    stats['j'].append(initJ)
    # ------------

    writer_min = SummaryWriter('runs/min')
    writer_max = SummaryWriter('runs/max')
    writer_opt = SummaryWriter('runs/opt')

    for i in range(0, N_ITERATION):
        determin_samples = sampling_from_det_pol(env, N_EPISODES, N_STEPS, det_param)
        # dyn_intervals = helper.build_mcrst_from_samples(determin_samples, N_MCRST_DYN, MIN_SPACE_VAL, MAX_SPACE_VAL)
        dyn_intervals = None
        abstraction.divide_samples(determin_samples, problem, help.getSeed(), intervals=dyn_intervals)
        abstraction.compute_abstract_tf(ds0, ENV_NOISE)

        abs_opt_pol = abs_updater.solve_mdp(abstraction.get_container(), intervals=dyn_intervals)

        # tensorboard
        for mcrst, ap in enumerate(abs_opt_pol):
            if len(ap) > 1:
                ap = ap[0]
            writer_opt.add_scalar('mcrst{}'.format(mcrst), ap, i)
        for mcrst, cont in enumerate(abstraction.get_container()):
            writer_min.add_scalar('mcrst{}'.format(mcrst), min(cont.keys()), i)
            writer_max.add_scalar('mcrst{}'.format(mcrst), max(cont.keys()), i)

        # ---- performance abstract policy ---
        first_states_ep = [d[0][0] for d in determin_samples]
        absJ = estimate_performance_abstract_policy(env, N_EPISODES, N_STEPS, abs_opt_pol, first_states_ep,
                                                    dyn_intervals, INTERVALS)
        # ------------------------------------

        fictitious_samples = sampling_abstract_optimal_pol(abs_opt_pol, determin_samples, det_param, dyn_intervals,
                                                           INTERVALS)
        det_param = det_upd.batch_gradient_update(det_param, fictitious_samples)

        j = env.computeJ(det_param, 0, N_EPISODES)
        estj = helper.estimate_J_from_samples(determin_samples, GAMMA)

        print("{} - Updated deterministic policy parameter: {}".format(i, det_param))
        print("Updated performance measure: {}".format(j))
        print("Updated estimated performance measure: {}\n".format(estj))
        visualizer.show_values(det_param, j, estj, absJ)

        file_writer.writerow([det_param, j, estj, absJ])

        # PLOTTER INFO
        stats['param'].append(det_param)
        stats['j'].append(j)
        stats['sampleJ'].append(estj)
        stats['abstractJ'].append(absJ)
        # ------------

    visualizer.save_image()
    writer_min.close()
    writer_max.close()
    writer_opt.close()
    return stats, opt_par4vis, optJ4vis
