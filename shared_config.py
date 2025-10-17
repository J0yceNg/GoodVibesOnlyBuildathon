#!/usr/bin/env python3
"""
Shared configuration for live control
This file is read by FairLane Controller and modified by FastAPI
"""

from dataclasses import dataclass, field
from typing import Dict
import threading

@dataclass
class LiveConfig:
    """
    Configuration that can be modified in real-time
    Thread-safe for concurrent access
    """
    
    # AI Control
    ai_enabled: bool = True
    
    # Priority Weights (higher = more important)
    priority_weights: Dict[str, float] = field(default_factory=lambda: {
        'emergency': 5.0,
        'accessible_vehicle': 4.0,
        'olympic_shuttle': 3.0,
        'regular_bus': 2.0,
        'car': 1.0
    })
    
    # Detection Range
    detection_distance: int = 150  # meters
    
    # Timing Parameters
    min_green_time: int = 15   # seconds
    max_green_time: int = 60   # seconds
    extension_time: int = 10   # seconds per priority vehicle

    # --- Runtime state (for controller lifecycle) ---
    _running: bool = True
    _paused: bool = False
    _restart: bool = False
    _stop: bool = False
    _speed: float = 1.0
    _current_step: int = 0
    
    # Thread lock for safe updates
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    
    # === GETTER METHODS (Thread-safe) ===
    
    def is_ai_enabled(self) -> bool:
        with self._lock:
            return self.ai_enabled
    
    def get_priority_weight(self, vehicle_type: str) -> float:
        with self._lock:
            return self.priority_weights.get(vehicle_type, 1.0)
    
    def get_detection_distance(self) -> int:
        with self._lock:
            return self.detection_distance
    
    def get_min_green_time(self) -> int:
        with self._lock:
            return self.min_green_time
    
    def get_max_green_time(self) -> int:
        with self._lock:
            return self.max_green_time
    
    def get_extension_time(self) -> int:
        with self._lock:
            return self.extension_time
    
    # === SETTER METHODS (Thread-safe) - Dev C's API will call these ===
    
    def set_ai_enabled(self, enabled: bool):
        with self._lock:
            self.ai_enabled = enabled
            print(f"[CONFIG] AI {'enabled' if enabled else 'disabled'}")
    
    def update_priority_weights(self, weights: Dict[str, float]):
        with self._lock:
            self.priority_weights.update(weights)
            print(f"[CONFIG] Priority weights updated: {weights}")
    
    def set_detection_distance(self, distance: int):
        with self._lock:
            if 50 <= distance <= 500:  # Safety bounds
                self.detection_distance = distance
                print(f"[CONFIG] Detection distance set to {distance}m")
            else:
                print(f"[CONFIG] Invalid detection distance: {distance}")
    
    def update_timing(self, min_green: int = None, max_green: int = None, extension: int = None):
        with self._lock:
            if min_green is not None and 5 <= min_green <= 60:
                self.min_green_time = min_green
            if max_green is not None and 30 <= max_green <= 180:
                self.max_green_time = max_green
            if extension is not None and 1 <= extension <= 30:
                self.extension_time = extension
            print(f"[CONFIG] Timing updated: min={self.min_green_time}s, max={self.max_green_time}s, ext={self.extension_time}s")
    
    # === UTILITY METHODS ===
    
    def get_all_config(self) -> dict:
        """Get all configuration as dictionary (for API responses)"""
        with self._lock:
            return {
                'ai_enabled': self.ai_enabled,
                'priority_weights': self.priority_weights.copy(),
                'detection_distance': self.detection_distance,
                'timing': {
                    'min_green': self.min_green_time,
                    'max_green': self.max_green_time,
                    'extension': self.extension_time
                }
            }
    
    def reset_to_defaults(self):
        """Reset all parameters to default values"""
        with self._lock:
            self.ai_enabled = True
            self.priority_weights = {
                'emergency': 5.0,
                'accessible_vehicle': 4.0,
                'olympic_shuttle': 3.0,
                'regular_bus': 2.0,
                'car': 1.0
            }
            self.detection_distance = 150
            self.min_green_time = 15
            self.max_green_time = 60
            self.extension_time = 10
            print("[CONFIG] Reset to default values")

        # === LIFECYCLE / RUNTIME HOOKS (used by controller) ===

    # start/stop/restart
    def start_simulation(self):
        with self._lock:
            self._running = True
            self._paused = False
            self._stop = False
            self._restart = False
            self._current_step = 0
            print("[CONFIG] Simulation started")

    def mark_simulation_stopped(self):
        with self._lock:
            self._running = False
            print("[CONFIG] Simulation stopped")

    def is_simulation_running(self) -> bool:
        with self._lock:
            return self._running and not self._stop

    def should_simulation_stop(self) -> bool:
        with self._lock:
            return self._stop

    def should_simulation_restart(self) -> bool:
        with self._lock:
            return self._restart

    # pause/resume
    def pause_simulation(self):
        with self._lock:
            self._paused = True
            print("[CONFIG] Simulation paused")

    def resume_simulation(self):
        with self._lock:
            self._paused = False
            print("[CONFIG] Simulation resumed")

    def is_simulation_paused(self) -> bool:
        with self._lock:
            return self._paused

    # external signals (e.g., from API/UI)
    def request_stop(self):
        with self._lock:
            self._stop = True
            print("[CONFIG] Stop requested")

    def request_restart(self):
        with self._lock:
            self._restart = True
            print("[CONFIG] Restart requested")

    # speed/step (used for pacing and simple telemetry)
    def set_simulation_speed(self, speed: float):
        with self._lock:
            if speed <= 0:
                speed = 1.0
            self._speed = float(speed)
            print(f"[CONFIG] Simulation speed set to {self._speed}x")

    def get_simulation_speed(self) -> float:
        with self._lock:
            return self._speed

    def update_current_step(self, step: int):
        with self._lock:
            self._current_step = int(step)

    def get_current_step(self) -> int:
        with self._lock:
            return self._current_step


# Global instance - shared between FastAPI and simulation
live_config = LiveConfig()