# eval_dqn_flags.py
from pathlib import Path
import numpy as np
import gymnasium as gym
import sumo_rl, traci

from stable_baselines3 import DQN

from rl.reward_wrappers import make_weighted_reward_env, _lanes_with_green
from rl.flags_sim import get_priority_flags_by_time
from rl.obs_wrappers import AppendFlagsObsWrapper

ENV_KW = dict(
    net_file='local_sumo/net/olympic_corridor.net.xml',
    route_file='local_sumo/routes/olympic_corridor_fixed.rou.xml',
    use_gui=False,
    num_seconds=120,
    delta_time=5,
)

MODEL_PATH = Path("models/dqn_flags.zip")

def dedupe(seq):
    s=set(); out=[]
    for x in seq:
        if x not in s: out.append(x); s.add(x)
    return out

def main():
    assert MODEL_PATH.exists(), f"Missing {MODEL_PATH}. Run train_dqn_flags.py first."

    # Build env (single, not vectorized) so we can introspect each step
    base = gym.make('sumo-rl-v0', **ENV_KW)
    base.reset()
    tls = traci.trafficlight.getIDList()[0]
    lanes = dedupe(traci.trafficlight.getControlledLanes(tls))

    env = make_weighted_reward_env(
        base_env=base, tls_id=tls, lane_ids=lanes,
        cap_per_lane=20, bonus_per_flagged_green=0.30,
        flag_weight=2.5, flags_provider=get_priority_flags_by_time
    )
    env = AppendFlagsObsWrapper(env, tls_id=tls, lane_ids=lanes,
                                flags_provider=get_priority_flags_by_time)

    model = DQN.load(str(MODEL_PATH))

    obs, info = env.reset()
    total = 0.0
    steps = 0
    total_flagged = 0
    total_served  = 0

    while True:
        action, _ = model.predict(obs, deterministic=True)
        obs, r, term, trunc, _ = env.step(int(action))
        total += float(r); steps += 1

        # Count flags and served flags at this tick
        flags = get_priority_flags_by_time(tls, lanes)
        flagged_lanes = [l for l,v in flags.items() if v==1]
        if flagged_lanes:
            total_flagged += 1
            green = set(_lanes_with_green(tls))
            if any(l in green for l in flagged_lanes):
                total_served += 1

        if term or trunc: break

    env.close()
    served_rate = (total_served / total_flagged) if total_flagged else 0.0
    print(f"Episode steps: {steps}")
    print(f"TOTAL reward:  {total:.4f}")
    print(f"Flags present: {total_flagged} ticks; served: {total_served}  (rate={served_rate:.2f})")

if __name__ == "__main__":
    main()