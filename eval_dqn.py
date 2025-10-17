# eval_dqn.py
from pathlib import Path
import numpy as np
import gymnasium as gym
import sumo_rl
import traci

from rl.reward_wrappers import make_weighted_reward_env
from rl.priority_flags import get_priority_flags

ENV_KW = dict(
    net_file='local_sumo/net/olympic_corridor.net.xml',
    route_file='local_sumo/routes/olympic_corridor_fixed.rou.xml',
    use_gui=False,
    num_seconds=120,
    delta_time=5,
)

MODEL_PATH = Path("models/dqn_custom_reward.zip")

def make_wrapped_env():
    base = gym.make('sumo-rl-v0', **ENV_KW)
    obs, info = base.reset()
    tls_id = traci.trafficlight.getIDList()[0]
    env = make_weighted_reward_env(base, tls_id, flags_provider=get_priority_flags)
    return env

def total_queue_now(tls_id: str) -> int:
    lanes = traci.trafficlight.getControlledLanes(tls_id)
    # dedupe
    seen, uniq = set(), []
    for l in lanes:
        if l not in seen:
            uniq.append(l); seen.add(l)
    return int(sum(traci.lane.getLastStepHaltingNumber(l) for l in uniq))

def main():
    from stable_baselines3 import DQN

    assert MODEL_PATH.exists(), f"Model not found: {MODEL_PATH}"
    env = make_wrapped_env()
    model = DQN.load(str(MODEL_PATH))

    obs, info = env.reset()
    tls_id = traci.trafficlight.getIDList()[0]

    done = False
    total_reward = 0.0
    step = 0
    queues = []

    while True:
        action, _ = model.predict(obs, deterministic=True)
        obs, r, term, trunc, info = env.step(int(action))
        total_reward += float(r)
        step += 1
        q = total_queue_now(tls_id)
        queues.append(q)
        if term or trunc:
            break

    env.close()
    print(f"Episode steps: {step}")
    print(f"TOTAL reward: {total_reward:.4f}")
    print(f"Mean queue:   {np.mean(queues):.2f} (min {np.min(queues)}, max {np.max(queues)})")

if __name__ == "__main__":
    main()