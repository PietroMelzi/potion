import gym
from lqg1D.policy import StochasticPolicy as sp, DeterministicPolicy as dp
from lqg1D import estimator as e
import torch

env = gym.make('LQG1D-v0')
N_SAMPLES = 2000
N_MACROSTATES = 5
N_MAX_STEPS = 20
INIT_DETERMINISTIC_PARAM = -0.2

# constants for stochastic policy
INIT_MU = 0.
INIT_OMEGA = 1.
INIT_LR = 0.01

det_pol = dp(INIT_DETERMINISTIC_PARAM)
samples = []

for i in range(0, N_SAMPLES):
    env.reset()
    episode = []

    for j in range (0, N_MAX_STEPS):
        state = env.get_state()
        det_pol.train()
        action = det_pol(torch.from_numpy(state).float())
        new_state, r, done, info = env.step(action.detach().numpy())

        # print("[{}] - State = {}, Action = {}, Reward = {}, Next state = {}".format(i, state, action.detach().numpy(), r, new_state))
        # store each step I get
        episode.append([state[0], action[0], r, new_state[0]])
        state = new_state

    # store each episode I get
    samples.append(episode)

state_sampled = []
for sam in samples:
    for ep in sam:
        state_sampled.append(ep[0])

# estimate of the macrostate distribution using the samples I have
estimate_mcrst_dist = e.estimate_mcrst_dist(state_sampled, N_MACROSTATES, True, -env.max_pos, env.max_pos)

# let's calculate a different stochastic policy for every macrostate
st_policy = []
for i in range(0, N_MACROSTATES):
    st_policy.append(sp(INIT_MU, INIT_OMEGA, INIT_LR))

for i in range(0, N_SAMPLES):
    for j in range(0, len(samples[i])):
        mcrst = e.get_mcrst(samples[i][j][0], -env.max_pos, env.max_pos, N_MACROSTATES)

        grad_log_pol_mu, grad_log_pol_omega = st_policy[mcrst].gradient_log_policy(samples[i][j][1])

        # quantities used to perform gradient ascent
        grad_mu = grad_log_pol_mu / estimate_mcrst_dist[mcrst]
        grad_omega = grad_log_pol_omega / estimate_mcrst_dist[mcrst]
        st_policy[mcrst].update_parameters(grad_mu, grad_omega)

for i in range(0, N_MACROSTATES):
    par = st_policy[i].parameters()
    print("[MCRST{}]".format(i))
    print([p for p in par])
