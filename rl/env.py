import gymnasium as gym
import numpy as np
import traci

class SumoSignalEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, cfg_path, tls_id, lane_ids, decision_dt=5, max_queue_cap=20):
        super().__init__()
        self.cfg_path = cfg_path
        self.tls_id = tls_id
        self.lane_ids = lane_ids
        self.decision_dt = decision_dt
        self.max_queue_cap = max_queue_cap

        obs_dim = len(lane_ids) + 2 + len(lane_ids)  # queues + phase+time + priority flags (stub)
        self.observation_space = gym.spaces.Box(low=0.0, high=1.0, shape=(obs_dim,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(2)  # extend or switch

    def _norm(self, x, cap): return min(x, cap) / cap

    def _get_obs(self):
        # queues (normalized)
        queues = [self._norm(traci.lane.getLastStepHaltingNumber(l), self.max_queue_cap)
                  for l in self.lane_ids]
        # TLS phase + time-in-phase
        phase = traci.trafficlight.getPhase(self.tls_id)
        phase_norm = phase / max(1, traci.trafficlight.getPhaseNumber(self.tls_id)-1)
        time_in_phase = traci.trafficlight.getNextSwitch(self.tls_id) - traci.simulation.getTime()
        tip_norm = max(0.0, min(1.0, time_in_phase / 60.0))
        # priority flags (stub: zeros; will be fed by Dev C later)
        prio = [0.0 for _ in self.lane_ids]
        return np.array(queues + [phase_norm, tip_norm] + prio, dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        traci.start(["sumo", "-c", self.cfg_path, "--step-length", "1"])
        # (optional) set TLS to known starting phase
        return self._get_obs(), {}

    def step(self, action):
        if action == 0:
            # extend: we just advance sim for decision_dt without switching
            pass
        else:
            # switch safely (yellow/all-red automatically handled if program configured)
            traci.trafficlight.setPhase(self.tls_id, (traci.trafficlight.getPhase(self.tls_id) + 1))

        # advance simulation for decision window
        for _ in range(self.decision_dt):
            traci.simulationStep()

        obs = self._get_obs()
        # reward is Stage 2; for Step 1 return 0 to validate plumbing
        reward = 0.0
        terminated = traci.simulation.getMinExpectedNumber() <= 0
        truncated = False
        info = {}
        if terminated:
            traci.close()
        return obs, reward, terminated, truncated, info

    def close(self):
        if traci.isLoaded():
            traci.close()