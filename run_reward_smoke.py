# run_reward_smoke.py  (run from lovelyHackathon/)
import gymnasium as gym
import sumo_rl
from rl.reward_wrappers import make_weighted_reward_env
from rl.priority_flags import get_priority_flags

ENV_KW = dict(
    net_file='local_sumo/net/mini.net.xml',
    route_file='local_sumo/routes/mini.rou.xml',
    use_gui=False,
    num_seconds=120,
    delta_time=5,
)

# Base env
base = gym.make('sumo-rl-v0', **ENV_KW)

# Discover the single TLS id after reset
obs, info = base.reset()
import traci
tls_ids = traci.trafficlight.getIDList()
assert tls_ids, "No TLS found"
TLS = tls_ids[0]

# Wrap with our reward
env = make_weighted_reward_env(
    base_env=base,
    tls_id=TLS,
    lane_ids=None,                        # auto-detect
    cap_per_lane=20,
    bonus_per_flagged_green=0.2,
    flags_provider=get_priority_flags,    # stubbed to 0 for now
)

# Run one episode with random actions; print our custom rewards
obs, info = env.reset()
total = 0.0
t = 0
terminated = truncated = False
while not (terminated or truncated):
    action = env.action_space.sample()
    obs, r, terminated, truncated, info = env.step(action)
    total += r
    t += 1
    print(f"t={t:02d}, r={r:.4f}")
print("TOTAL:", round(total, 4))
env.close()