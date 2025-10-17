# train_dqn_flags.py
import os
from pathlib import Path
import gymnasium as gym
import sumo_rl, traci

from rl.reward_wrappers import make_weighted_reward_env
from rl.flags_sim import get_priority_flags_by_time
from rl.obs_wrappers import AppendFlagsObsWrapper

# ---------- SPEED HINT ----------
# Headless + LibSUMO is much faster
os.environ.setdefault("LIBSUMO_AS_TRACI", "1")

# ---------- ENV CONFIG ----------
ENV_KW = dict(
    net_file   ='local_sumo/net/olympic_corridor.net.xml',
    route_file ='local_sumo/routes/olympic_corridor_fixed.rou.xml',
    use_gui=False,
    num_seconds=120,   # keep short for smoke tests; corridor supports up to 3600s
    delta_time=5,
)

SEED = 11
LOG_DIR = Path("logs/dqn_flags"); LOG_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR = Path("models"); MODEL_DIR.mkdir(parents=True, exist_ok=True)

def make_env():
    # Base env and initial reset to attach TraCI
    base = gym.make('sumo-rl-v0', **ENV_KW)
    base.reset(seed=SEED)
    tls_id = traci.trafficlight.getIDList()[0]

    # Discover the controlled (incoming) lanes once
    lanes = traci.trafficlight.getControlledLanes(tls_id)
    lane_ids = []
    seen=set()
    for l in lanes:
        if l not in seen:
            lane_ids.append(l); seen.add(l)

    # Wrap with reward that uses flags (stronger incentive, moderate weight)
    env = make_weighted_reward_env(
        base_env=base,
        tls_id=tls_id,
        lane_ids=lane_ids,
        cap_per_lane=20,                  # tune if rewards too tiny/large
        bonus_per_flagged_green=0.30,     # +0.3 per tick if flagged lane is green
        flag_weight=2.5,                  # flagged queues count 2.5x in penalty
        flags_provider=get_priority_flags_by_time,
    )

    # Append flag bits to observation so policy can "see" them
    env = AppendFlagsObsWrapper(
        env, tls_id=tls_id, lane_ids=lane_ids,
        flags_provider=get_priority_flags_by_time
    )
    return env

def main():
    from stable_baselines3 import DQN
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.vec_env import DummyVecEnv
    from stable_baselines3.common.utils import set_random_seed

    set_random_seed(SEED)

    def _thunk():
        e = make_env()
        e = Monitor(e, str(LOG_DIR))
        return e

    venv = DummyVecEnv([_thunk])

    # Light(ish) config for a short run; bump later
    model = DQN(
        "MlpPolicy",
        venv,
        learning_rate=3e-4,
        buffer_size=20_000,
        learning_starts=1_000,
        batch_size=64,
        gamma=0.99,
        train_freq=(1, "step"),
        gradient_steps=1,
        target_update_interval=500,
        exploration_fraction=0.2,
        exploration_final_eps=0.05,
        policy_kwargs=dict(net_arch=[64, 64]),
        verbose=1,
        tensorboard_log=str(LOG_DIR),
        seed=SEED,
    )

    total_timesteps = 5_000  # start here; increase once it’s working
    try:
        model.learn(total_timesteps=total_timesteps, progress_bar=True)
    finally:
        venv.close()

    out = MODEL_DIR / "dqn_flags.zip"
    model.save(str(out))
    print(f"Saved flags model to {out}")

if __name__ == "__main__":
    main()