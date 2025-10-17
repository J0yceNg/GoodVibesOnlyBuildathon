#!/usr/bin/env python3
"""
FairLane - Dynamic Transit Lane Optimizer
AI-powered traffic signal priority system for Olympic corridor
"""

import traci
import sys
import time
import os
import asyncio
import json
from collections import defaultdict
from typing import Dict, List, Set, Optional
from datetime import datetime, timedelta

# FastAPI and WebSocket imports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sumolib

# Local imports
from traffic_predictor import TrafficPredictor
from shared_config import live_config, sim_control

# FastAPI setup
app = FastAPI()

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests
class SpeedRequest(BaseModel):
    speed: float

class AIConfigRequest(BaseModel):
    enabled: bool

class DetectionDistanceRequest(BaseModel):
    distance: int

class TimingConfigRequest(BaseModel):
    min_green: int = None
    max_green: int = None
    extension: int = None

class ConnectionManager:
    """Manages WebSocket connections for broadcasting simulation data"""
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

# Configuration paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(BASE_DIR, "olympic_corridor.net.xml")


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


class FairLaneController:
    """
    Traffic signal controller with LIVE CONTROLS
    """
    
    def __init__(self):
        # Traffic light IDs
        self.traffic_lights = []
        self.stats = {
            'total_vehicles': 0,
            'priority_vehicles_served': defaultdict(int),
            'avg_waiting_time': defaultdict(list),
            'signal_extensions': 0,
            'ai_preemptive_actions': 0,
            'predictions_made': 0,
            'high_congestion_prevented': 0
        }
        
        # Network data and boundary for WebSocket broadcasting
        self.network_data = None
        self.boundary = None

        try:
            self.predictor = TrafficPredictor()
            self.use_prediction = True
            print("✓ AI Prediction Model loaded successfully")
        except Exception as e:
            self.predictor = None
            self.use_prediction = False
            print(f"⚠ Running without AI prediction model: {e}")
        
        self.simulation_start_time = datetime(2025, 10, 17, 8, 0, 0)
        self.prediction_history = []

    def get_vehicle_type(self, vehicle_id):
        """Get the type of vehicle for priority calculation"""
        try:
            vtype = traci.vehicle.getTypeID(vehicle_id)
            return vtype
        except:
            return 'car'
    
    def get_priority_score(self, vehicle_id):
        """Calculate priority score for a vehicle - NOW USES LIVE CONFIG"""
        vtype = self.get_vehicle_type(vehicle_id)
        return live_config.get_priority_weight(vtype)  # CHANGED: Read from config
    
    def get_current_datetime(self, simulation_step):
        """Convert simulation step (seconds) to datetime"""
        return self.simulation_start_time + timedelta(seconds=simulation_step)
    
    def get_vehicle_count_at_intersection(self, tl_id):
        """Count vehicles approaching this traffic light"""
        controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
        total_vehicles = 0
        
        for lane in set(controlled_lanes):
            try:
                total_vehicles += traci.lane.getLastStepVehicleNumber(lane)
            except:
                continue
        
        return total_vehicles

    def predict_congestion_at_intersection(self, tl_id, step):
        """
        Get AI prediction - CHECKS IF AI IS ENABLED
        """
        # NEW: Check if AI is enabled via live config
        if not live_config.is_ai_enabled():
            return None, None
        
        if not self.use_prediction:
            return None, None
        
        try:
            current_time = self.get_current_datetime(step)
            vehicle_count = self.get_vehicle_count_at_intersection(tl_id)
            
            prediction = self.predictor.predict_congestion(
                tl_id, current_time, vehicle_count
            )
            
            level = self.predictor.get_congestion_level_label(prediction)
            
            self.prediction_history.append({
                'step': step,
                'time': current_time,
                'intersection': tl_id,
                'prediction': prediction,
                'level': level,
                'vehicle_count': vehicle_count
            })
            
            self.stats['predictions_made'] += 1
            
            return prediction, level
            
        except Exception as e:
            print(f"[{tl_id}] Prediction error: {e}")
            return None, None

    def detect_priority_vehicles(self, tl_id):
        """
        Detect priority vehicles - NOW USES LIVE DETECTION DISTANCE
        """
        controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
        
        priority_vehicles = []
        max_priority = 0
        vehicle_types = []
        
        # NEW: Get detection distance from live config
        detection_distance = live_config.get_detection_distance()
        
        for lane in set(controlled_lanes):
            vehicles_on_lane = traci.lane.getLastStepVehicleIDs(lane)
            
            for veh_id in vehicles_on_lane:
                try:
                    pos = traci.vehicle.getLanePosition(veh_id)
                    lane_length = traci.lane.getLength(lane)
                    distance_to_light = lane_length - pos
                    
                    # CHANGED: Use live config detection distance
                    if distance_to_light <= detection_distance:
                        priority = self.get_priority_score(veh_id)
                        vtype = self.get_vehicle_type(veh_id)
                        
                        if priority > 1.0:
                            priority_vehicles.append((veh_id, priority, vtype))
                            max_priority = max(max_priority, priority)
                            vehicle_types.append(vtype)
                            
                except traci.exceptions.TraCIException:
                    continue
        
        has_priority = len(priority_vehicles) > 0
        return has_priority, max_priority, vehicle_types
    
    def control_signal(self, tl_id, current_phase, time_in_phase, step):
        """
        AI-Enhanced signal control - NOW USES LIVE CONFIG
        """
        
        # Check for priority vehicles
        has_priority, priority_score, vehicle_types = self.detect_priority_vehicles(tl_id)
        
        # Get AI prediction (respects ai_enabled flag)
        predicted_congestion, congestion_level = self.predict_congestion_at_intersection(tl_id, step)
        
        # Log predictions periodically
        if predicted_congestion and step % 300 == 0:
            print(f"[AI PREDICTION] {tl_id}: {congestion_level} congestion in 15min ({predicted_congestion:.2f})")
        
        should_extend = False
        decision_reason = None
        
        # NEW: Get timing parameters from live config
        max_green_time = live_config.get_max_green_time()
        
        # Priority vehicle logic (using live config weights)
        if has_priority:
            if 'emergency' in vehicle_types:
                print(f"[{tl_id}] EMERGENCY vehicle detected - extending green")
                self.stats['priority_vehicles_served']['emergency'] += 1
                self.stats['signal_extensions'] += 1
                should_extend = True
                decision_reason = "emergency_vehicle"
            
            elif 'accessible_vehicle' in vehicle_types:
                print(f"[{tl_id}] ACCESSIBLE vehicle detected - extending green")
                self.stats['priority_vehicles_served']['accessible_vehicle'] += 1
                self.stats['signal_extensions'] += 1
                should_extend = True
                decision_reason = "accessible_vehicle"
            
            elif 'olympic_shuttle' in vehicle_types:
                print(f"[{tl_id}] OLYMPIC shuttle detected - extending green")
                self.stats['priority_vehicles_served']['olympic_shuttle'] += 1
                self.stats['signal_extensions'] += 1
                should_extend = True
                decision_reason = "olympic_shuttle"
            
            elif 'regular_bus' in vehicle_types:
                if time_in_phase < max_green_time:  # CHANGED: Use live config
                    print(f"[{tl_id}] Bus detected - extending green")
                    self.stats['priority_vehicles_served']['regular_bus'] += 1
                    self.stats['signal_extensions'] += 1
                    should_extend = True
                    decision_reason = "regular_bus"
        
        # AI Proactive Control (only if AI enabled)
        if not should_extend and predicted_congestion:
            SEVERE_THRESHOLD = 0.70
            HEAVY_THRESHOLD = 0.55
            
            if predicted_congestion >= SEVERE_THRESHOLD:
                vehicle_count = self.get_vehicle_count_at_intersection(tl_id)
                print(f"[{tl_id}] 🤖 AI ALERT: Severe congestion predicted!")
                print(f"    Current: {vehicle_count} vehicles")
                print(f"    Forecast: {predicted_congestion:.2f} congestion level")
                print(f"    Action: Extending green phase preemptively")
                should_extend = True
                decision_reason = "ai_severe_prediction"
                self.stats['ai_preemptive_actions'] += 1
                self.stats['high_congestion_prevented'] += 1
            
            elif predicted_congestion >= HEAVY_THRESHOLD and time_in_phase < max_green_time - 10:
                vehicle_count = self.get_vehicle_count_at_intersection(tl_id)
                print(f"[{tl_id}] 🤖 AI: HEAVY congestion predicted ({predicted_congestion:.2f}) - minor extension")
                print(f"    Current vehicles: {vehicle_count}")
                should_extend = True
                decision_reason = "ai_heavy_prediction"
                self.stats['ai_preemptive_actions'] += 1
        
        # Log decision
        if decision_reason:
            if not hasattr(self, 'decision_log'):
                self.decision_log = []
            self.decision_log.append({
                'step': step,
                'intersection': tl_id,
                'reason': decision_reason,
                'prediction': predicted_congestion,
                'had_priority': has_priority
            })
        
        return should_extend
    
    async def run_simulation(self, gui=True, api_mode=False):
        """
        Main simulation loop with start/stop/restart control and WebSocket broadcasting
        """
        
        sumoBinary = "sumo-gui" if gui else "sumo"
        sumoCmd = [sumoBinary, "-c", "olympic_corridor.sumocfg"]
        
        print("=" * 60)
        print("FairLane Dynamic Transit Lane Optimizer")
        print("🎮 LIVE CONTROL MODE ENABLED")
        print("=" * 60)
        
        if api_mode:
            print("\n⏳ Waiting for START signal from dashboard...")
            print("   Dashboard can start simulation via POST /api/simulation/start")
            
            # Wait for start signal
            while not sim_control.is_simulation_running():
                await asyncio.sleep(0.5)
                if sim_control.should_simulation_stop():
                    print("❌ Simulation cancelled before start")
                    return
            
            print("✓ START signal received!")
        else:
            # Auto-start if not in API mode
            sim_control.start_simulation()
        
        # Load network data before starting TraCI
        self.network_data = build_network_data()
        self.boundary = self.network_data["boundary"]
        
        # Broadcast network info to all clients
        network_info = {
            "type": "network_info",
            "data": self.network_data
        }
        await manager.broadcast(network_info)
        print(f"✓ Sent network data: {len(self.network_data['roads'])} roads")
        
        # Start SUMO
        traci.start(sumoCmd)
        self.traffic_lights = traci.trafficlight.getIDList()
        
        print(f"\nMonitoring {len(self.traffic_lights)} intersections")
        
        config = live_config.get_all_config()
        print("\nCurrent Configuration:")
        print(f"  AI Enabled: {config['ai_enabled']}")
        print(f"  Detection Range: {config['detection_distance']}m")
        print(f"  Min/Max Green: {config['timing']['min_green']}/{config['timing']['max_green']}s")
        print("\n" + "=" * 60 + "\n")
        
        tl_phase_start = {tl: 0 for tl in self.traffic_lights}
        step = 0
        
        # Initialize cumulative statistics tracking for WebSocket
        cumulative_stats = {
            'total_wait_time': 0,
            'total_co2': 0,
            'total_delayed': 0,
            'total_samples': 0,
            'by_type': {}
        }
        
        try:
            while traci.simulation.getMinExpectedNumber() > 0:
                # Check for stop signal
                if sim_control.should_simulation_stop():
                    print("\n🛑 STOP signal received - terminating simulation")
                    break
                
                # Check for restart signal
                if sim_control.should_simulation_restart():
                    print("\n🔄 RESTART signal received")
                    traci.close()
                    await asyncio.sleep(1)
                    # Restart will be handled by wrapper
                    break
                
                # Handle pause
                while sim_control.is_simulation_paused():
                    print("⏸️  Simulation paused...", end='\r')
                    await asyncio.sleep(0.5)
                    if sim_control.should_simulation_stop():
                        break
                
                if sim_control.should_simulation_stop():
                    break
                
                # Simulation speed control
                speed = sim_control.get_simulation_speed()
                if speed != 1.0:
                    # Adjust delay based on speed (lower speed = more delay)
                    delay = (1.0 / speed) * 0.01  # Base delay of 10ms
                    await asyncio.sleep(delay)
                
                # Normal simulation step
                traci.simulationStep()
                step += 1
                
                # Update current step in config
                sim_control.update_current_step(step)
                
                self.stats['total_vehicles'] = traci.vehicle.getIDCount()
                
                # Control each traffic light
                for tl_id in self.traffic_lights:
                    try:
                        current_phase = traci.trafficlight.getPhase(tl_id)
                        time_in_phase = step - tl_phase_start[tl_id]
                        
                        should_extend = self.control_signal(tl_id, current_phase, time_in_phase, step)
                        
                        min_green_time = live_config.get_min_green_time()
                        extension_time = live_config.get_extension_time()
                        
                        if should_extend and time_in_phase >= min_green_time:
                            programs = traci.trafficlight.getAllProgramLogics(tl_id)
                            if programs:
                                current_program = programs[0]
                                phases = list(current_program.phases)
                                
                                if current_phase < len(phases):
                                    phases[current_phase] = traci.trafficlight.Phase(
                                        phases[current_phase].duration + extension_time,
                                        phases[current_phase].state,
                                        phases[current_phase].minDur,
                                        phases[current_phase].maxDur
                                    )
                                    
                                    logic = traci.trafficlight.Logic(
                                        current_program.programID,
                                        current_program.type,
                                        current_program.currentPhaseIndex,
                                        phases
                                    )
                                    traci.trafficlight.setProgramLogic(tl_id, logic)
                        
                        new_phase = traci.trafficlight.getPhase(tl_id)
                        if new_phase != current_phase:
                            tl_phase_start[tl_id] = step
                            
                    except traci.exceptions.TraCIException:
                        continue
                
                # ===== WebSocket Broadcasting =====
                # Collect vehicle data
                vehicle_ids = traci.vehicle.getIDList()
                vehicles = []
                for vid in vehicle_ids:
                    veh_data = get_vehicle_data(vid, self.boundary)
                    if veh_data:
                        vehicles.append(veh_data)
                
                # Collect traffic light data
                traffic_lights = []
                for tid in self.traffic_lights:
                    tl_data = get_traffic_light_state(tid, self.boundary)
                    if tl_data:
                        traffic_lights.append(tl_data)
                
                # Calculate current frame statistics by vehicle type
                vehicle_types_data = {}
                current_wait_time = 0
                current_co2 = 0
                current_delayed_count = 0
                
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
                            'count': vehicle_types_data.get(veh_type, {}).get('count', 0),
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
                        "by_type": vehicle_type_stats,
                        "signal_extensions": self.stats['signal_extensions'],
                        "ai_preemptive_actions": self.stats['ai_preemptive_actions']
                    }
                }
                
                # Broadcast to all connected clients
                await manager.broadcast(simulation_data)
                
                # Control update rate (60 FPS)
                await asyncio.sleep(0.016)
                
                # Print statistics periodically
                if step % 300 == 0:
                    self.print_statistics(step)
        
        finally:
            print("\n" + "=" * 60)
            print("Simulation Complete")
            print("=" * 60)
            self.print_final_statistics()
            traci.close()
            sim_control.mark_simulation_stopped()
    
    def print_statistics(self, step):
        """Print current statistics"""
        print(f"\n--- Time: {step}s ({step//60} minutes) ---")
        print(f"Total vehicles in simulation: {self.stats['total_vehicles']}")
        print(f"Signal extensions: {self.stats['signal_extensions']}")
        
        # Show live config status
        print(f"AI Status: {'ENABLED' if live_config.is_ai_enabled() else 'DISABLED'}")
        
        if live_config.is_ai_enabled():
            print(f"AI predictions made: {self.stats['predictions_made']}")
            print(f"AI preemptive actions: {self.stats['ai_preemptive_actions']}")
        
        print("Priority vehicles served:")
        for vtype, count in self.stats['priority_vehicles_served'].items():
            weight = live_config.get_priority_weight(vtype)
            print(f"  {vtype}: {count} (weight: {weight}x)")
    
    def print_final_statistics(self):
        """Print final simulation statistics"""
        print("\n" + "=" * 60)
        print("FINAL STATISTICS")
        print("=" * 60)
        print(f"Total vehicles processed: {self.stats['total_vehicles']}")
        print(f"Total signal extensions: {self.stats['signal_extensions']}")
        print(f"AI preemptive actions: {self.stats['ai_preemptive_actions']}")
        print(f"AI predictions made: {self.stats['predictions_made']}")
        print(f"High congestion events prevented: {self.stats['high_congestion_prevented']}")
        
        print("\nPriority Vehicles Served:")
        total_priority = 0
        for vtype, count in sorted(self.stats['priority_vehicles_served'].items()):
            weight = live_config.get_priority_weight(vtype)
            print(f"  {vtype}: {count} vehicles (priority weight: {weight}x)")
            total_priority += count
        
        print(f"\nTotal priority vehicles served: {total_priority}")
        print("=" * 60)


# ===== FastAPI Endpoints =====

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time simulation data"""
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


@app.get("/")
async def root():
    """Root endpoint - API status"""
    return {
        "message": "FairLane TraCI WebSocket Server",
        "status": "running",
        "ws_url": "ws://localhost:8000/ws",
        "connections": len(manager.active_connections)
    }


@app.get("/health")
async def health():
    """Health check endpoint with detailed status"""
    return {
        "status": "healthy",
        "connections": len(manager.active_connections),
        "simulation": {
            "running": sim_control.is_simulation_running(),
            "paused": sim_control.is_simulation_paused(),
            "current_step": sim_control.get_current_step(),
            "speed": sim_control.get_simulation_speed()
        },
        "config": live_config.get_all_config()
    }


@app.get("/api/simulation/status")
async def get_simulation_status():
    """Get detailed simulation status"""
    return {
        "running": sim_control.is_simulation_running(),
        "paused": sim_control.is_simulation_paused(),
        "current_step": sim_control.get_current_step(),
        "speed": sim_control.get_simulation_speed(),
        "connections": len(manager.active_connections)
    }


@app.post("/api/simulation/start")
async def start_simulation():
    """Start the simulation"""
    if sim_control.is_simulation_running():
        return {"success": False, "message": "Simulation is already running"}
    
    sim_control.start_simulation()
    return {"success": True, "message": "Simulation started"}


@app.post("/api/simulation/stop")
async def stop_simulation():
    """Stop the simulation"""
    if not sim_control.is_simulation_running():
        return {"success": False, "message": "Simulation is not running"}
    
    sim_control.stop_simulation()
    return {"success": True, "message": "Stop signal sent"}


@app.post("/api/simulation/pause")
async def pause_simulation():
    """Pause the simulation"""
    if not sim_control.is_simulation_running():
        return {"success": False, "message": "Simulation is not running"}
    
    if sim_control.is_simulation_paused():
        return {"success": False, "message": "Simulation is already paused"}
    
    sim_control.pause_simulation()
    return {"success": True, "message": "Simulation paused"}


@app.post("/api/simulation/resume")
async def resume_simulation():
    """Resume the simulation"""
    if not sim_control.is_simulation_running():
        return {"success": False, "message": "Simulation is not running"}
    
    if not sim_control.is_simulation_paused():
        return {"success": False, "message": "Simulation is not paused"}
    
    sim_control.resume_simulation()
    return {"success": True, "message": "Simulation resumed"}


@app.post("/api/simulation/restart")
async def restart_simulation():
    """Restart the simulation"""
    sim_control.restart_simulation()
    return {"success": True, "message": "Restart signal sent"}


@app.post("/api/simulation/speed")
async def set_simulation_speed(request: SpeedRequest):
    """Set simulation speed (0.1 to 10.0)"""
    if request.speed < 0.1 or request.speed > 10.0:
        return {"success": False, "message": "Speed must be between 0.1 and 10.0"}
    
    sim_control.set_simulation_speed(request.speed)
    return {"success": True, "message": f"Simulation speed set to {request.speed}x"}


@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    return live_config.get_all_config()


@app.post("/api/config/ai")
async def set_ai_enabled(request: AIConfigRequest):
    """Enable or disable AI predictions"""
    live_config.set_ai_enabled(request.enabled)
    return {"success": True, "message": f"AI {'enabled' if request.enabled else 'disabled'}"}


@app.post("/api/config/detection-distance")
async def set_detection_distance(request: DetectionDistanceRequest):
    """Set detection distance for priority vehicles"""
    if request.distance < 50 or request.distance > 500:
        return {"success": False, "message": "Distance must be between 50 and 500 meters"}
    
    live_config.set_detection_distance(request.distance)
    return {"success": True, "message": f"Detection distance set to {request.distance}m"}


@app.post("/api/config/timing")
async def set_timing(request: TimingConfigRequest):
    """Update timing parameters"""
    live_config.update_timing(
        min_green=request.min_green,
        max_green=request.max_green,
        extension=request.extension
    )
    return {"success": True, "message": "Timing parameters updated", "config": live_config.get_all_config()}


@app.post("/api/config/reset")
async def reset_config():
    """Reset configuration to defaults"""
    live_config.reset_to_defaults()
    return {"success": True, "message": "Configuration reset to defaults", "config": live_config.get_all_config()}


@app.on_event("startup")
async def startup_event():
    """Start simulation in background when server starts"""
    print("=" * 60)
    print("FairLane TraCI WebSocket Server Starting")
    print("=" * 60)
    print(f"Base Directory: {BASE_DIR}")
    print(f"Network File: {NET_FILE}")
    print("=" * 60)
    
    # Start simulation as background task
    async def run_simulation_loop():
        while True:
            controller = FairLaneController()
            # In server mode, wait for API start signal (api_mode=True)
            await controller.run_simulation(gui=False, api_mode=True)
            
            # Check if restart was requested
            if not sim_control.should_simulation_restart():
                break
            
            print("\n🔄 Restarting simulation in 3 seconds...")
            sim_control.should_restart = False  # Reset flag
            await asyncio.sleep(3)
        
        print("👋 FairLane simulation terminated")
    
    asyncio.create_task(run_simulation_loop())


def main():
    """Main entry point with restart loop"""
    gui = True
    api_mode = False
    use_fastapi = False
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--no-gui":
            gui = False
        elif sys.argv[1] == "--api":
            api_mode = True
            print("🌐 API Mode: Simulation controlled by dashboard")
        elif sys.argv[1] == "--server":
            use_fastapi = True
            print("🌐 FastAPI Server Mode: Starting with WebSocket support")
    
    if use_fastapi:
        # Run as FastAPI server with WebSocket support
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    else:
        # Run standalone simulation (original behavior)
        async def run_standalone():
            while True:
                controller = FairLaneController()
                await controller.run_simulation(gui=gui, api_mode=api_mode)
                
                # Check if restart was requested
                if not sim_control.should_simulation_restart():
                    break
                
                print("\n🔄 Restarting simulation in 3 seconds...")
                sim_control.should_restart = False  # Reset flag
                await asyncio.sleep(3)
            
            print("👋 FairLane terminated")
        
        # Run the async simulation
        asyncio.run(run_standalone())


if __name__ == "__main__":
    main()