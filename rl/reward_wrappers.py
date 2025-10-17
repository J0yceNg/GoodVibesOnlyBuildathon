# rl/reward_wrappers.py
import gymnasium as gym
import numpy as np
import traci
from typing import Callable, Dict, List, Optional

def _unique_controlled_lanes(tls_id: str) -> List[str]:
    lanes = traci.trafficlight.getControlledLanes(tls_id)
    seen, uniq = set(), []
    for l in lanes:
        if l not in seen:
            uniq.append(l); seen.add(l)
    return uniq

def _lanes_with_green(tls_id: str) -> List[str]:
    states = traci.trafficlight.getRedYellowGreenState(tls_id)
    links  = traci.trafficlight.getControlledLinks(tls_id)
    green_lanes = set()
    for idx, state in enumerate(states):
        if state in ("g", "G"):
            for inLane, _, _ in links[idx]:
                green_lanes.add(inLane)
    return list(green_lanes)

class WeightedDelayRewardWrapper(gym.RewardWrapper):
    """
    reward = - normalized weighted queue  +  bonus_per_flagged_green * (# flagged lanes currently green)
    """
    def __init__(
        self,
        env: gym.Env,
        tls_id: str,
        lane_ids: Optional[List[str]] = None,
        cap_per_lane: int = 20,
        bonus_per_flagged_green: float = 0.2,
        flags_provider: Optional[Callable[[str, List[str]], Dict[str, int]]] = None,
        flag_weight: float = 3.0,  # multiply queue weight for flagged lanes
    ):
        super().__init__(env)
        self.tls_id = tls_id
        self.lane_ids = lane_ids
        self.cap_per_lane = cap_per_lane
        self.bonus_per_flagged_green = bonus_per_flagged_green
        self.flags_provider = flags_provider or (lambda tls, lanes: {l: 0 for l in lanes})
        self.flag_weight = flag_weight
        self._last = None  # debug snapshot

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        if self.lane_ids is None:
            self.lane_ids = _unique_controlled_lanes(self.tls_id)
        return obs, info

    def reward(self, _ignored_env_reward):
        # 1) queues now
        queues = np.array([traci.lane.getLastStepHaltingNumber(l) for l in self.lane_ids], dtype=float)
        # 2) current flags and weights
        flags = self.flags_provider(self.tls_id, self.lane_ids)  # {lane: 0/1}
        weights = np.array([1.0 + (self.flag_weight - 1.0) * flags.get(l, 0) for l in self.lane_ids], dtype=float)
        # 3) weighted delay cost & normalization
        cost = float((queues * weights).sum())
        norm = max(1.0, self.cap_per_lane * len(self.lane_ids))
        delay_term = - cost / norm
        # 4) bonus for serving flagged lanes now
        green = set(_lanes_with_green(self.tls_id))
        flagged_green = sum(flags.get(l, 0) for l in green)
        bonus_term = self.bonus_per_flagged_green * flagged_green
        total = delay_term + bonus_term
        # 5) keep a debug snapshot
        self._last = dict(
            t = traci.simulation.getTime(),
            lanes = list(self.lane_ids),
            queues = queues.tolist(),
            flags = {l:int(flags.get(l,0)) for l in self.lane_ids},
            weights = weights.tolist(),
            green = list(green),
            cost = cost, norm = norm,
            delay_term = float(delay_term),
            bonus_term = float(bonus_term),
            total = float(total),
        )
        return total

    def last_debug(self):
        return self._last

def make_weighted_reward_env(
    base_env: gym.Env,
    tls_id: str,
    lane_ids: Optional[List[str]] = None,
    cap_per_lane: int = 20,
    bonus_per_flagged_green: float = 0.2,
    flags_provider: Optional[Callable[[str, List[str]], Dict[str, int]]] = None,
    flag_weight: float = 3.0,
) -> gym.Env:
    return WeightedDelayRewardWrapper(
        base_env,
        tls_id=tls_id,
        lane_ids=lane_ids,
        cap_per_lane=cap_per_lane,
        bonus_per_flagged_green=bonus_per_flagged_green,
        flags_provider=flags_provider,
        flag_weight=flag_weight,
    )