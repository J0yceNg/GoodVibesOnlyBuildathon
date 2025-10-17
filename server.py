import asyncio
import json
from typing import Dict, List, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
import traci
import sumolib

app = FastAPI()

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
        print(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIM_DIR = os.path.join(BASE_DIR, "simulation")
SUMO_CONFIG = os.path.join(SIM_DIR, "olympic_corridor.sumocfg")
NET_FILE = os.path.join(SIM_DIR, "olympic_corridor.net.xml")

# Use headless SUMO for better performance
try:
    SUMO_BINARY = sumolib.checkBinary("sumo")
except Exception as e:
    print(f"Error finding SUMO binary: {e}")
    sys.exit(1)


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


async def run_simulation():
    """Main simulation loop with continuous restart."""
    # Load network data once (before starting TraCI)
    network_data = build_network_data()
    boundary = network_data["boundary"]
    
    while True:
        try:
            # Verify config file exists
            if not os.path.exists(SUMO_CONFIG):
                raise FileNotFoundError(f"SUMO config not found: {SUMO_CONFIG}")

            # Start SUMO with TraCI
            print(f"Starting SUMO simulation...")
            traci.start([
                SUMO_BINARY,
                "-c", SUMO_CONFIG,
                "--start",
                "--quit-on-end",
                "--step-length", "0.5",  # 100ms time steps
                "--no-warnings",
            ])
            
            print("✓ Simulation started successfully")
            
            # Send network info to all clients
            network_info = {
                "type": "network_info",
                "data": network_data
            }
            await manager.broadcast(network_info)
            print(f"✓ Sent network data: {len(network_data['roads'])} roads")
            
            # Initialize cumulative statistics tracking
            cumulative_stats = {
                'total_wait_time': 0,
                'total_co2': 0,
                'total_delayed': 0,
                'total_samples': 0,
                'by_type': {}  # type -> {wait_time, co2, speed, samples}
            }
            
            # Simulation loop
            step = 0
            steps_per_update = 1  # Increase this to 2, 3, or 4 to run simulation faster
            while traci.simulation.getMinExpectedNumber() > 0:
                # Run multiple simulation steps before updating visualization
                for _ in range(steps_per_update):
                    traci.simulationStep()
                    step += 1
                
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
                
                # Calculate current frame statistics by vehicle type
                vehicle_types_data = {}
                current_wait_time = 0
                current_co2 = 0
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
                    
                    current_wait_time += veh['waiting_time']
                    current_co2 += veh['co2']
                    
                    if veh['waiting_time'] > 10:
                        current_delayed_count += 1
                
                # Update cumulative statistics
                if len(vehicle_ids) > 0:
                    cumulative_stats['total_wait_time'] += current_wait_time
                    cumulative_stats['total_co2'] += current_co2
                    cumulative_stats['total_delayed'] += current_delayed_count
                    cumulative_stats['total_samples'] += len(vehicle_ids)
                    
                    # Update per-type cumulative stats
                    for veh_type, data in vehicle_types_data.items():
                        if veh_type not in cumulative_stats['by_type']:
                            cumulative_stats['by_type'][veh_type] = {
                                'total_wait_time': 0,
                                'total_co2': 0,
                                'total_speed': 0,
                                'total_count': 0
                            }
                        
                        cumulative_stats['by_type'][veh_type]['total_wait_time'] += data['total_wait_time']
                        cumulative_stats['by_type'][veh_type]['total_co2'] += data['total_co2']
                        cumulative_stats['by_type'][veh_type]['total_speed'] += data['total_speed']
                        cumulative_stats['by_type'][veh_type]['total_count'] += data['count']
                
                # Calculate cumulative averages per vehicle type
                vehicle_type_stats = {}
                for veh_type, data in cumulative_stats['by_type'].items():
                    if data['total_count'] > 0:
                        vehicle_type_stats[veh_type] = {
                            'count': vehicle_types_data.get(veh_type, {}).get('count', 0),  # Current count
                            'avg_wait_time': round(data['total_wait_time'] / data['total_count'], 1),
                            'avg_co2': round(data['total_co2'] / data['total_count'], 2),
                            'avg_speed': round(data['total_speed'] / data['total_count'], 1)
                        }
                
                # Calculate overall cumulative averages
                cumulative_avg_wait = round(cumulative_stats['total_wait_time'] / cumulative_stats['total_samples'], 1) if cumulative_stats['total_samples'] > 0 else 0
                cumulative_avg_co2 = round(cumulative_stats['total_co2'] / cumulative_stats['total_samples'], 2) if cumulative_stats['total_samples'] > 0 else 0
                cumulative_avg_delayed = round(cumulative_stats['total_delayed'] / cumulative_stats['total_samples'] * 100, 1) if cumulative_stats['total_samples'] > 0 else 0
                
                # Build update message
                simulation_data = {
                    "type": "simulation_update",
                    "step": step,
                    "time": round(traci.simulation.getTime(), 2),
                    "vehicles": vehicles,
                    "traffic_lights": traffic_lights,
                    "stats": {
                        "total_vehicles": len(vehicle_ids),
                        "avg_wait_time": cumulative_avg_wait,
                        "delayed_vehicles": current_delayed_count,
                        "delayed_percent": cumulative_avg_delayed,
                        "avg_co2": cumulative_avg_co2,
                        "total_co2": round(cumulative_stats['total_co2'], 2),
                        "collisions": traci.simulation.getCollidingVehiclesNumber(),
                        "by_type": vehicle_type_stats
                    }
                }
                
                # Broadcast to all connected clients
                await manager.broadcast(simulation_data)
                
                # Control update rate (60 FPS for faster visualization)
                await asyncio.sleep(0.016)
            
            print("Simulation completed, restarting...")
            traci.close()
            await asyncio.sleep(1)  # Brief pause before restart
            
        except Exception as e:
            print(f"❌ Simulation error: {e}")
            import traceback
            traceback.print_exc()
            try:
                traci.close()
            except:
                pass
            await asyncio.sleep(2)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send network data immediately on connection
        network_data = build_network_data()
        network_info_message = {
            "type": "network_info",
            "data": network_data
        }
        await websocket.send_json(network_info_message)
        print(f"✓ Sent network data to client: {len(network_data['roads'])} roads")
        
        # Keep connection alive and listen for potential client messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle client messages if needed (e.g., pause/resume simulation)
                message = json.loads(data)
                print(f"Received from client: {message}")
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket receive error: {e}")
                break
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)

@app.on_event("startup")
async def startup_event():
    # Start simulation in background
    print("=" * 60)
    print("SUMO TraCI WebSocket Server Starting")
    print("=" * 60)
    print(f"SUMO Binary: {SUMO_BINARY}")
    print(f"Config File: {SUMO_CONFIG}")
    print(f"Network File: {NET_FILE}")
    print("=" * 60)
    asyncio.create_task(run_simulation())

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