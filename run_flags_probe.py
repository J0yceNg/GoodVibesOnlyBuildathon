# run_flags_probe.py
import gymnasium as gym, sumo_rl, traci
from rl.reward_wrappers import make_weighted_reward_env
from rl.flags_sim import get_priority_flags_by_time

ENV_KW = dict(
    net_file='local_sumo/net/mini.net.xml',
    route_file='local_sumo/routes/mini.rou.xml',
    use_gui=False,
    num_seconds=120,  # our flags trigger at 30..90s and 90..120s
    delta_time=5,
)

# base env + attach TraCI
base = gym.make('sumo-rl-v0', **ENV_KW)
base.reset()
tls = traci.trafficlight.getIDList()[0]

# wrap with flags + bonus
env = make_weighted_reward_env(
    base_env=base,
    tls_id=tls,
    cap_per_lane=20,
    bonus_per_flagged_green=0.2,   # visible per tick when served
    flags_provider=get_priority_flags_by_time,
    flag_weight=3.0,               # flagged lanes counted 3× in delay
)

obs, info = env.reset()
tot = 0.0
step = 0
while True:
    # naive policy: alternate actions so we occasionally serve both phases
    act = step % env.action_space.n
    obs, r, term, trunc, info = env.step(act)
    dbg = env.last_debug() or {}
    tot += r; step += 1
    # Pretty print a compact breakdown
    t   = dbg.get("t"); fg = dbg.get("flags", {})
    grn = set(dbg.get("green", []))
    flanes = [l for l,v in fg.items() if v==1]
    served = [l for l in flanes if l in grn]
    print(f"t={t:5.1f}s  act={act}  r={r:+.3f}  "
          f"delay={dbg.get('delay_term',0):+.3f}  bonus={dbg.get('bonus_term',0):+.3f}  "
          f"flags={len(flanes)} served={len(served)}")
    if term or trunc:
        break

print(f"TOTAL={tot:.4f}")
env.close()