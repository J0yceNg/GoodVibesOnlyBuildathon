#!/usr/bin/env python3
"""
FairLane - Dynamic Transit Lane Optimizer
AI-powered traffic signal priority system for Olympic corridor
"""

import traci
import sys
import time
from collections import defaultdict
from traffic_predictor import TrafficPredictor
from datetime import datetime, timedelta
from shared_config import live_config

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
    
    def run_simulation(self, gui=True, api_mode=False):
        """
        Main simulation loop with start/stop/restart control
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
            while not live_config.is_simulation_running():
                time.sleep(0.5)
                if live_config.should_simulation_stop():
                    print("❌ Simulation cancelled before start")
                    return
            
            print("✓ START signal received!")
        else:
            # Auto-start if not in API mode
            live_config.start_simulation()
        
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
        
        try:
            while traci.simulation.getMinExpectedNumber() > 0:
                # Check for stop signal
                if live_config.should_simulation_stop():
                    print("\n🛑 STOP signal received - terminating simulation")
                    break
                
                # Check for restart signal
                if live_config.should_simulation_restart():
                    print("\n🔄 RESTART signal received")
                    traci.close()
                    time.sleep(1)
                    # Restart will be handled by wrapper
                    break
                
                # Handle pause
                while live_config.is_simulation_paused():
                    print("⏸️  Simulation paused...", end='\r')
                    time.sleep(0.5)
                    if live_config.should_simulation_stop():
                        break
                
                if live_config.should_simulation_stop():
                    break
                
                # Simulation speed control
                speed = live_config.get_simulation_speed()
                if speed != 1.0:
                    # Adjust delay based on speed (lower speed = more delay)
                    delay = (1.0 / speed) * 0.01  # Base delay of 10ms
                    time.sleep(delay)
                
                # Normal simulation step
                traci.simulationStep()
                step += 1
                
                # Update current step in config
                live_config.update_current_step(step)
                
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
                
                if step % 300 == 0:
                    self.print_statistics(step)
        
        finally:
            print("\n" + "=" * 60)
            print("Simulation Complete")
            print("=" * 60)
            self.print_final_statistics()
            traci.close()
            live_config.mark_simulation_stopped()
    
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
    
    # ... rest of your methods (print_final_statistics, save_prediction_data) remain the same ...

def main():
    """Main entry point with restart loop"""
    gui = True
    api_mode = False
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--no-gui":
            gui = False
        elif sys.argv[1] == "--api":
            api_mode = True
            print("🌐 API Mode: Simulation controlled by dashboard")
    
    while True:
        controller = FairLaneController()
        controller.run_simulation(gui=gui, api_mode=api_mode)
        
        # Check if restart was requested
        if not live_config.should_simulation_restart():
            break
        
        print("\n🔄 Restarting simulation in 3 seconds...")
        live_config.should_restart = False  # Reset flag
        time.sleep(3)
    
    print("👋 FairLane terminated")


if __name__ == "__main__":
    main()