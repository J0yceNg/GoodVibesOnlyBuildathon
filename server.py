import asyncio
import json
from typing import Dict, List, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
import traci
import sumolib
import threading
import subprocess
from shared_config import live_config

app = FastAPI()

# FairLane controller process/thread
fairlane_process = None
fairlane_thread = None
fairlane_controller = None  # Will be set when controller starts

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[WebSocket] Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"[WebSocket] Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WebSocket] Error sending to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(BASE_DIR, "olympic_corridor.net.xml")

# Network data cache - loaded once and reused
_network_data_cache = None

def get_connection_manager():
    """Get the ConnectionManager instance for external use"""
    return manager


# ============================================
# API MODELS
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
    distance: int

class TimingParams(BaseModel):
    min_green: int = None
    max_green: int = None
    extension: int = None

class SimulationSpeed(BaseModel):
    speed: float  # 0.1 to 10.0


def build_network_data() -> Dict:
    """
    Build network geometry from SUMO network file with lane-level detail.
    Returns a simple coordinate system based on network boundaries.
    """
    try:
        net = sumolib.net.readNet(NET_FILE)
        
        # Get network boundaries
        boundary = net.getBoundary()
        min_x, min_y = boundary[0], boundary[1]
        max_x, max_y = boundary[2], boundary[3]
        
        # Calculate center
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        
        # Build road features with lane-level detail
        roads = []
        edges = net.getEdges()
        
        width = max_x - min_x
        height = max_y - min_y
        scale = max(width, height)
        
        for edge in edges:
            edge_id = edge.getID()
            
            # Skip internal junction edges
            if edge_id.startswith(':'):
                continue
            
            # Get all lanes for this edge
            lanes = edge.getLanes()
            lane_data = []
            
            if lanes and scale > 0:
                for lane in lanes:
                    lane_shape = lane.getShape()
                    if lane_shape and len(lane_shape) >= 2:
                        # Normalize lane coordinates
                        normalized_coords = []
                        for x, y in lane_shape:
                            norm_x = 2 * (x - center_x) / scale
                            norm_y = 2 * (y - center_y) / scale
                            normalized_coords.append([float(norm_x), float(norm_y)])
                        
                        # Calculate lane direction (angle) from first to last point
                        import math
                        p1 = lane_shape[0]
                        p2 = lane_shape[-1]
                        dx = p2[0] - p1[0]
                        dy = p2[1] - p1[1]
                        angle = math.atan2(dy, dx) * 180 / math.pi
                        
                        lane_data.append({
                            "id": lane.getID(),
                            "index": lane.getIndex(),
                            "coordinates": normalized_coords,
                            "width": float(lane.getWidth()),
                            "speed": float(lane.getSpeed()),
                            "angle": round(float(angle), 1)
                        })
                
                if lane_data:
                    roads.append({
                        "id": edge_id,
                        "lanes": lane_data,
                        "from": edge.getFromNode().getID(),
                        "to": edge.getToNode().getID(),
                        "num_lanes": len(lane_data)
                    })
        
        print(f"Loaded {len(roads)} roads with lane detail from network")
        
        # Get all junction positions from the network
        junctions = []
        nodes = net.getNodes()
        for node in nodes:
            node_id = node.getID()
            coord = node.getCoord()
            
            # Normalize junction coordinates
            norm_x = 2 * (coord[0] - center_x) / scale
            norm_y = 2 * (coord[1] - center_y) / scale
            
            junctions.append({
                "id": node_id,
                "x": float(norm_x),
                "y": float(norm_y),
                "type": node.getType()
            })
        
        print(f"Loaded {len(junctions)} junction positions from network")
        
        return {
            "roads": roads,
            "junctions": junctions,
            "boundary": {
                "min_x": float(min_x),
                "min_y": float(min_y),
                "max_x": float(max_x),
                "max_y": float(max_y),
                "center_x": float(center_x),
                "center_y": float(center_y),
                "width": float(max_x - min_x),
                "height": float(max_y - min_y)
            }
        }
    
    except Exception as e:
        print(f"Error loading network data: {e}")
        import traceback
        traceback.print_exc()
        return {
            "roads": [],
            "junctions": [],
            "boundary": {
                "min_x": 0, "min_y": 0,
                "max_x": 500, "max_y": 500,
                "center_x": 250, "center_y": 250,
                "width": 500, "height": 500
            }
        }


def normalize_position(x: float, y: float, boundary: Dict) -> tuple:
    """Convert SUMO coordinates to normalized viewport coordinates."""
    center_x = boundary["center_x"]
    center_y = boundary["center_y"]
    width = boundary["width"]
    height = boundary["height"]
    scale = max(width, height)
    
    if scale > 0:
        norm_x = 2 * (x - center_x) / scale
        norm_y = 2 * (y - center_y) / scale
    else:
        norm_x = 0
        norm_y = 0
    
    return float(norm_x), float(norm_y)


def get_vehicle_data(veh_id: str, boundary: Dict) -> Optional[Dict]:
    """Extract vehicle information with normalized coordinates."""
    try:
        position = traci.vehicle.getPosition(veh_id)
        norm_x, norm_y = normalize_position(position[0], position[1], boundary)
        
        return {
            "id": veh_id,
            "x": norm_x,
            "y": norm_y,
            "speed": round(traci.vehicle.getSpeed(veh_id), 2),
            "angle": round(traci.vehicle.getAngle(veh_id), 1),
            "road_id": traci.vehicle.getRoadID(veh_id),
            "lane_id": traci.vehicle.getLaneID(veh_id),
            "waiting_time": round(traci.vehicle.getWaitingTime(veh_id), 1),
            "co2": round(traci.vehicle.getCO2Emission(veh_id), 2),
            "type": traci.vehicle.getTypeID(veh_id)
        }
    except Exception as e:
        print(f"Error getting vehicle {veh_id} data: {e}")
        return None


def get_traffic_light_state(tl_id: str, boundary: Dict) -> Optional[Dict]:
    """Extract traffic light information with controlled directions."""
    try:
        state = traci.trafficlight.getRedYellowGreenState(tl_id)
        current_phase = traci.trafficlight.getPhase(tl_id)
        next_switch = traci.trafficlight.getNextSwitch(tl_id)
        
        # Get controlled links to find position and directions
        controlled_links = traci.trafficlight.getControlledLinks(tl_id)
        
        # Try to get junction position and controlled directions
        position = None
        controlled_lanes = []
        
        # Get actual junction position from network file
        try:
            # Traffic light ID should match a junction ID
            import sumolib
            net = sumolib.net.readNet(NET_FILE)
            junction = net.getNode(tl_id)
            if junction:
                junc_coord = junction.getCoord()
                norm_x, norm_y = normalize_position(junc_coord[0], junc_coord[1], boundary)
                position = {"x": norm_x, "y": norm_y}
        except Exception as e:
            # Fallback: use first controlled lane endpoint if junction lookup fails
            if controlled_links and len(controlled_links) > 0:
                first_link = controlled_links[0]
                if first_link and len(first_link) > 0:
                    lane_id = first_link[0][0]
                    try:
                        lane_shape = traci.lane.getShape(lane_id)
                        if lane_shape:
                            pos = lane_shape[-1]
                            norm_x, norm_y = normalize_position(pos[0], pos[1], boundary)
                            position = {"x": norm_x, "y": norm_y}
                    except Exception:
                        pass
        
        if controlled_links and len(controlled_links) > 0:
            
            # Get direction information for each controlled link
            # Use a dict to track unique directions and avoid duplicates
            seen_directions = {}
            
            for i, link in enumerate(controlled_links):
                if link and len(link) > 0 and i < len(state):
                    from_lane = link[0][0]
                    try:
                        lane_shape = traci.lane.getShape(from_lane)
                        if lane_shape and len(lane_shape) >= 2:
                            # Calculate direction from last two points of incoming lane
                            p1 = lane_shape[-2]
                            p2 = lane_shape[-1]
                            dx = p2[0] - p1[0]
                            dy = p2[1] - p1[1]
                            
                            # Normalize and convert to world coordinates
                            import math
                            angle = math.atan2(dy, dx) * 180 / math.pi
                            rounded_angle = round(angle, 1)
                            
                            # Group signals by direction (within 15 degrees)
                            # This prevents showing multiple signals for the same approach
                            angle_key = round(rounded_angle / 15) * 15
                            
                            # Only add if we haven't seen this direction yet, or if it has a different state
                            if angle_key not in seen_directions:
                                seen_directions[angle_key] = {
                                    "signal_index": i,
                                    "signal_state": state[i],
                                    "angle": rounded_angle
                                }
                            elif state[i] in ['G', 'g']:  # Prefer green signals if duplicate
                                seen_directions[angle_key] = {
                                    "signal_index": i,
                                    "signal_state": state[i],
                                    "angle": rounded_angle
                                }
                    except Exception as e:
                        pass
            
            # Convert dict back to list
            controlled_lanes = list(seen_directions.values())
        
        return {
            "id": tl_id,
            "state": state,
            "phase": current_phase,
            "next_switch": round(next_switch, 1),
            "position": position,
            "controlled_lanes": controlled_lanes
        }
    except Exception as e:
        print(f"Error getting traffic light {tl_id} data: {e}")
        return None


async def broadcast_simulation_update():
    """
    Broadcast simulation updates to all connected WebSocket clients.
    This function is called by the FairLane controller during the simulation loop.
    """
    global _network_data_cache
    
    # Check if TraCI is connected
    try:
        step = traci.simulation.getTime()
    except:
        # TraCI not connected yet
        return
    
    # Load network data if not cached
    if _network_data_cache is None:
        _network_data_cache = build_network_data()
    
    boundary = _network_data_cache["boundary"]
    
    try:
        # Collect simulation data
        vehicle_ids = traci.vehicle.getIDList()
        tl_ids = traci.trafficlight.getIDList()
        
        # Get vehicle data
        vehicles = []
        for vid in vehicle_ids:
            veh_data = get_vehicle_data(vid, boundary)
            if veh_data:
                vehicles.append(veh_data)
        
        # Get traffic light data
        traffic_lights = []
        for tid in tl_ids:
            tl_data = get_traffic_light_state(tid, boundary)
            if tl_data:
                traffic_lights.append(tl_data)
        
        # Calculate statistics by vehicle type
        vehicle_types_data = {}
        current_delayed_count = 0  # Vehicles waiting more than 10 seconds
        
        for veh in vehicles:
            veh_type = veh['type']
            if veh_type not in vehicle_types_data:
                vehicle_types_data[veh_type] = {
                    'count': 0,
                    'total_wait_time': 0,
                    'total_co2': 0,
                    'total_speed': 0
                }
            
            vehicle_types_data[veh_type]['count'] += 1
            vehicle_types_data[veh_type]['total_wait_time'] += veh['waiting_time']
            vehicle_types_data[veh_type]['total_co2'] += veh['co2']
            vehicle_types_data[veh_type]['total_speed'] += veh['speed']
            
            if veh['waiting_time'] > 10:
                current_delayed_count += 1
        
        # Calculate averages per vehicle type (for this frame)
        vehicle_type_stats = {}
        for veh_type, data in vehicle_types_data.items():
            if data['count'] > 0:
                vehicle_type_stats[veh_type] = {
                    'count': data['count'],
                    'avg_wait_time': round(data['total_wait_time'] / data['count'], 1),
                    'avg_co2': round(data['total_co2'] / data['count'], 2),
                    'avg_speed': round(data['total_speed'] / data['count'], 1)
                }
        
        # Calculate overall averages (for this frame)
        avg_wait = round(sum(v['waiting_time'] for v in vehicles) / len(vehicles), 1) if vehicles else 0
        avg_co2 = round(sum(v['co2'] for v in vehicles) / len(vehicles), 2) if vehicles else 0
        delayed_percent = round(current_delayed_count / len(vehicles) * 100, 1) if vehicles else 0
        total_co2 = round(sum(v['co2'] for v in vehicles), 2)
        
        # Build update message
        simulation_data = {
            "type": "simulation_update",
            "step": int(step),
            "time": round(step, 2),
            "vehicles": vehicles,
            "traffic_lights": traffic_lights,
            "stats": {
                "total_vehicles": len(vehicle_ids),
                "avg_wait_time": avg_wait,
                "delayed_vehicles": current_delayed_count,
                "delayed_percent": delayed_percent,
                "avg_co2": avg_co2,
                "total_co2": total_co2,
                "collisions": traci.simulation.getCollidingVehiclesNumber(),
                "by_type": vehicle_type_stats
            }
        }
        
        # Broadcast to all connected clients
        await manager.broadcast(simulation_data)
        
    except Exception as e:
        print(f"[WebSocket] Error broadcasting update: {e}")


# ============================================
# CONFIGURATION CONTROL ENDPOINTS
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


# ============================================
# SIMULATION CONTROL ENDPOINTS
# ============================================

@app.post("/api/simulation/start")
async def start_simulation():
    """Start the simulation - sends signal to FairLane controller"""
    # Since the simulation auto-starts, this endpoint mainly confirms status
    # or can be used to restart if the simulation was stopped
    
    if live_config.is_simulation_running():
        return {
            "success": True,
            "status": "already_running",
            "message": "Simulation is already running"
        }
    
    # Signal the controller to start (if it was previously stopped)
    live_config.start_simulation()
    
    return {
        "success": True,
        "status": "started",
        "message": "Simulation started"
    }

@app.post("/api/simulation/stop")
async def stop_simulation():
    """Stop the simulation - sends signal to FairLane controller"""
    if not live_config.is_simulation_running():
        raise HTTPException(status_code=400, detail="Simulation not running")
    
    live_config.request_stop()
    
    return {
        "success": True,
        "status": "stopped",
        "message": "Simulation stop requested"
    }

@app.post("/api/simulation/pause")
async def pause_simulation():
    """Pause the simulation - sends signal to FairLane controller"""
    if not live_config.is_simulation_running():
        raise HTTPException(status_code=400, detail="Simulation not running")
    
    if live_config.is_simulation_paused():
        raise HTTPException(status_code=400, detail="Simulation already paused")
    
    live_config.pause_simulation()
    
    return {
        "success": True,
        "status": "paused",
        "message": "Simulation paused"
    }

@app.post("/api/simulation/resume")
async def resume_simulation():
    """Resume the simulation - sends signal to FairLane controller"""
    if not live_config.is_simulation_paused():
        raise HTTPException(status_code=400, detail="Simulation not paused")
    
    live_config.resume_simulation()
    
    return {
        "success": True,
        "status": "running",
        "message": "Simulation resumed"
    }

@app.post("/api/simulation/restart")
async def restart_simulation():
    """Restart the simulation - sends signal to FairLane controller"""
    live_config.request_restart()
    
    return {
        "success": True,
        "status": "restarting",
        "message": "Simulation restart requested"
    }

@app.post("/api/simulation/speed")
async def set_simulation_speed(data: SimulationSpeed):
    """Set simulation speed (0.1x to 10x)"""
    if data.speed < 0.1 or data.speed > 10.0:
        raise HTTPException(status_code=400, detail="Speed must be between 0.1 and 10.0")
    
    live_config.set_simulation_speed(data.speed)
    
    return {
        "success": True,
        "speed": live_config.get_simulation_speed()
    }

@app.get("/api/simulation/status")
async def get_simulation_status():
    """Get current simulation status from shared config"""
    return {
        "running": live_config.is_simulation_running(),
        "paused": live_config.is_simulation_paused(),
        "current_step": live_config.get_current_step(),
        "time": float(live_config.get_current_step()),
        "speed": live_config.get_simulation_speed()
    }


# ============================================
# WEBSOCKET ENDPOINT
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send network data immediately on connection
        global _network_data_cache
        if _network_data_cache is None:
            _network_data_cache = build_network_data()
        
        network_info_message = {
            "type": "network_info",
            "data": _network_data_cache
        }
        await websocket.send_json(network_info_message)
        print(f"[WebSocket] ✓ Sent network data to client: {len(_network_data_cache['roads'])} roads")
        
        # Keep connection alive and listen for potential client messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle client messages if needed (e.g., pause/resume simulation)
                message = json.loads(data)
                print(f"[WebSocket] Received from client: {message}")
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"[WebSocket] Receive error: {e}")
                break
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
    finally:
        manager.disconnect(websocket)

@app.on_event("startup")
async def startup_event():
    """Start the server and automatically launch the simulation"""
    global fairlane_thread, fairlane_controller
    
    print("=" * 60)
    print("SUMO TraCI WebSocket Server Starting")
    print("=" * 60)
    print(f"Network File: {NET_FILE}")
    print("=" * 60)
    
    # Automatically start the FairLane controller
    def run_fairlane():
        global fairlane_controller
        try:
            # Import here to avoid circular dependency
            from fairlane_controller import FairLaneController
            
            print("\n🚀 Starting FairLane Controller...")
            
            # Create controller with broadcast callback
            fairlane_controller = FairLaneController(policy_mode="ensemble")
            fairlane_controller.broadcast_callback = broadcast_simulation_update
            
            # Auto-start the simulation (not in API mode, so it starts immediately)
            fairlane_controller.run_simulation(gui=False, api_mode=False)
        except Exception as e:
            print(f"❌ Error running FairLane controller: {e}")
            import traceback
            traceback.print_exc()
        finally:
            fairlane_controller = None
    
    # Start FairLane controller in background thread
    fairlane_thread = threading.Thread(target=run_fairlane, daemon=True)
    fairlane_thread.start()
    
    print("✅ FairLane controller launched in background")
    print("=" * 60)

@app.get("/")
async def root():
    return {
        "message": "SUMO TraCI WebSocket Server",
        "status": "running",
        "ws_url": "ws://localhost:8000/ws",
        "connections": len(manager.active_connections)
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "connections": len(manager.active_connections)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")