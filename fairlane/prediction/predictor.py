# fairlane/prediction/predictor.py
from __future__ import annotations
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# Import YOUR original predictor class
from traffic_predictor import TrafficPredictor as LegacyPredictor


class TrafficPredictor:
    """
    Adapter that wraps your original TrafficPredictor (traffic_predictor.py)
    and returns a normalized dict the controller expects.
    """

    def __init__(self, model_path: Optional[str] = "traffic_predictor_model.pkl"):
        # Your original class loads the model in its __init__
        self._legacy = LegacyPredictor(model_path=model_path)

    def predict_congestion(
        self,
        tl_id: str,
        step: int,
        horizon_s: int = 900,
        context: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        Controller passes:
          - tl_id: SUMO TLS id (we treat it as intersection_id in your model)
          - step: simulation seconds since start
          - context: {"current_time": datetime, "vehicle_count": int}
        Returns a dict with keys: congestion_prob, expected_delay_s, hot_approaches, confidence
        """
        if context is None:
            context = {}

        current_time = context.get("current_time")
        vehicle_count = context.get("vehicle_count")

        # Fallbacks if controller didn't pass context (it does in your code)
        if current_time is None:
            # Your original model accepts datetime; reconstruct from sim start (8:00)
            sim_start = datetime(2025, 10, 17, 8, 0, 0)
            current_time = sim_start + timedelta(seconds=step)
        if vehicle_count is None:
            # If we don't know, assume 0 (your model uses vehicle_history, so it's still okay)
            vehicle_count = 0

        # Call your original model (returns a float in [0,1])
        prob = float(self._legacy.predict_congestion(tl_id, current_time, vehicle_count))

        # Optional label from your original helper—kept for completeness
        if hasattr(self._legacy, "get_congestion_level_label"):
            try:
                level = self._legacy.get_congestion_level_label(prob)
            except Exception:
                level = None
        else:
            level = None

        # Normalize to dict shape the controller expects
        return {
            "tl_id": tl_id,
            "horizon_s": int(horizon_s),
            "congestion_prob": prob,          # main signal
            "expected_delay_s": 0.0,          # not available in your original model
            "hot_approaches": [],             # not available; leave empty
            "confidence": 0.7,                # simple fixed confidence (optional)
            "level": level,                   # optional convenience
        }
