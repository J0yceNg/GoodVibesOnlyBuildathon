# rl/flags_sim.py
from typing import Dict, List
import traci

def get_priority_flags_by_time(tls_id: str, lane_ids: List[str]) -> Dict[str, int]:
    """
    Simulate priority: flag lane_ids[0] from t∈[30,90) seconds,
    then lane_ids[1] from t∈[90,120) seconds. Else 0.
    Adjust windows/lanes as you wish.
    """
    t = traci.simulation.getTime()
    flags = {l: 0 for l in lane_ids}
    if len(lane_ids) >= 1 and 30 <= t < 90:
        flags[lane_ids[0]] = 1
    if len(lane_ids) >= 2 and 90 <= t < 120:
        flags[lane_ids[1]] = 1
    return flags