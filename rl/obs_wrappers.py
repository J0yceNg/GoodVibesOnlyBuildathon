# rl/obs_wrappers.py
import gymnasium as gym
import numpy as np
from typing import List, Dict, Callable, Optional

class AppendFlagsObsWrapper(gym.ObservationWrapper):
    """
    Appends a 0/1 vector of lane flags (ordered by lane_ids) to the base observation.
    Requires lane_ids known at construction time (we fetch them after base.reset()).
    """
    def __init__(self, env: gym.Env, tls_id: str, lane_ids: List[str],
                 flags_provider: Optional[Callable[[str, List[str]], Dict[str, int]]] = None):
        super().__init__(env)
        self.tls_id = tls_id
        self.lane_ids = list(lane_ids)
        self.flags_provider = flags_provider or (lambda tls, lanes: {l: 0 for l in lanes})
        base_low, base_high = self.observation_space.low, self.observation_space.high
        add_low  = np.zeros((len(self.lane_ids),), dtype=np.float32)
        add_high = np.ones((len(self.lane_ids),),  dtype=np.float32)
        self.observation_space = gym.spaces.Box(
            low=np.concatenate([base_low, add_low]),
            high=np.concatenate([base_high, add_high]),
            dtype=np.float32
        )

    def observation(self, obs):
        flags = self.flags_provider(self.tls_id, self.lane_ids)
        vec = np.array([float(flags.get(l,0)) for l in self.lane_ids], dtype=np.float32)
        return np.concatenate([np.array(obs, dtype=np.float32), vec], axis=0)