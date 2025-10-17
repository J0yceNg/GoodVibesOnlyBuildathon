# Dev C's FastAPI server (api.py)
from fastapi import FastAPI
from pydantic import BaseModel
from shared_config import live_config  # Import YOUR shared config

app = FastAPI()

# ============================================
# MODELS
# ============================================

class AIToggle(BaseModel):
    enabled: bool

class PriorityWeights(BaseModel):
    emergency: float = None
    accessible_vehicle: float = None
    olympic_shuttle: float = None
    regular_bus: float = None
    car: float = None

class DetectionRange(BaseModel):
    distance: int  # meters

class TimingParams(BaseModel):
    min_green: int = None
    max_green: int = None
    extension: int = None

# ============================================
# ENDPOINTS
# ============================================

@app.post("/api/control/ai")
async def toggle_ai(data: AIToggle):
    """Enable/disable AI predictions"""
    live_config.set_ai_enabled(data.enabled)
    return {"success": True, "ai_enabled": live_config.is_ai_enabled()}

@app.post("/api/control/priorities")
async def update_priorities(data: PriorityWeights):
    """Update priority weights"""
    weights = {}
    if data.emergency is not None:
        weights['emergency'] = data.emergency
    if data.accessible_vehicle is not None:
        weights['accessible_vehicle'] = data.accessible_vehicle
    if data.olympic_shuttle is not None:
        weights['olympic_shuttle'] = data.olympic_shuttle
    if data.regular_bus is not None:
        weights['regular_bus'] = data.regular_bus
    if data.car is not None:
        weights['car'] = data.car
    
    live_config.update_priority_weights(weights)
    return {"success": True, "weights": live_config.priority_weights}

@app.post("/api/control/detection")
async def update_detection(data: DetectionRange):
    """Update detection range"""
    live_config.set_detection_distance(data.distance)
    return {"success": True, "distance": live_config.get_detection_distance()}

@app.post("/api/control/timing")
async def update_timing(data: TimingParams):
    """Update timing parameters"""
    live_config.update_timing(
        min_green=data.min_green,
        max_green=data.max_green,
        extension=data.extension
    )
    return {"success": True, "timing": live_config.get_all_config()['timing']}

@app.get("/api/config")
async def get_config():
    """Get all current configuration"""
    return live_config.get_all_config()

@app.post("/api/config/reset")
async def reset_config():
    """Reset to default values"""
    live_config.reset_to_defaults()
    return {"success": True, "config": live_config.get_all_config()}