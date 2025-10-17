# fairlane/rl/agent.py
from __future__ import annotations
from typing import Dict, Any, Optional

class RLAgent:
    """
    Adapter around your DQN eval code to present a stable get_action(state) API.
    """
    def __init__(self, checkpoint: Optional[str] = None, use_flags: bool = True):
        self.use_flags = use_flags
        try:
            if use_flags:
                from eval_dqn_flags import load_agent as _load
            else:
                from eval_dqn import load_agent as _load
        except Exception as e:
            raise RuntimeError(f"Could not import RL eval module: {e}") from e
        self._agent = _load(checkpoint)

        # Map DQN action index -> controller verb.
        # If your verify_obs_actions.py says otherwise, edit this map.
        self._idx2verb = {
            0: "normal",
            1: "extend",
            2: "shorten",
            3: "switch",
            4: "hold",
        }

    def get_action(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # If your eval expects a vector, convert dict->vector right here.
        act_idx, q_vals = self._agent.act(state)
        verb = self._idx2verb.get(int(act_idx), "normal")
        return {
            "action": verb,
            "hold_s": float(state.get("suggested_hold_s", 0.0)),
            "q_values": q_vals,
            "policy_id": "dqn_flags" if self.use_flags else "dqn",
        }