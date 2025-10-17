from typing import Dict, List

def get_priority_flags(tls_id: str, lane_ids: List[str]) -> Dict[str, int]:
    """
    Return a dict {lane_id: 0/1} indicating whether the lane currently has priority.
    Stubbed to 0 for now; later you'll plug in Dev C's feed (Emergency, Accessible, etc.).
    """
    return {lane: 0 for lane in lane_ids}

# Optional: a weighted scheme for classes you may receive later.
DEFAULT_CLASS_WEIGHTS = {
    "Emergency": 5.0,
    "Accessible": 3.0,
    "Olympic":   2.0,
    "Public":    1.5,
}