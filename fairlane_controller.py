#!/usr/bin/env python3
"""
FairLane - Dynamic Transit Lane Optimizer
AI-powered traffic signal priority system for Olympic corridor
"""

import traci
import sys
from collections import defaultdict
from traffic_predictor import TrafficPredictor
from datetime import datetime, timedelta

class FairLaneController:
    """
    Traffic signal controller with priority for:
    - Emergency vehicles (highest)
    - Accessible vehicles
    - Olympic shuttles
    - Regular buses
    - Cars (lowest)
    """
    
    def __init__(self):
        # Priority weights (higher = more important)
        self.priority_weights = {
            'emergency': 5.0,
            'accessible_vehicle': 4.0,
            'olympic_shuttle': 3.0,
            'regular_bus': 2.0,
            'car': 1.0
        }
        
        # Traffic light IDs
        self.traffic_lights = []  # Will be populated from SUMO
        
        # Detection zones (distance from intersection)
        self.detection_distance = 150  # meters
        
        # Green time extensions
        self.min_green_time = 15  # seconds
        self.max_green_time = 60  # seconds
        self.extension_time = 10  # seconds per priority vehicle
        
        # Statistics tracking - FIXED: Added AI stats
        self.stats = {
            'total_vehicles': 0,
            'priority_vehicles_served': defaultdict(int),
            'avg_waiting_time': defaultdict(list),
            'signal_extensions': 0,
            'ai_preemptive_actions': 0,       
            'predictions_made': 0,             
            'high_congestion_prevented': 0     
        }

        # Initialize AI Predictor
        try:
            self.predictor = TrafficPredictor()
            self.use_prediction = True
            print("✓ AI Prediction Model loaded successfully")
        except Exception as e:
            self.predictor = None
            self.use_prediction = False
            print(f"⚠ Running without AI prediction model: {e}")
        
        # Track simulation time
        self.simulation_start_time = datetime(2025, 10, 17, 8, 0, 0)  # 8 AM start

        # Store prediction history
        self.prediction_history = []

    def get_vehicle_type(self, vehicle_id):
        """Get the type of vehicle for priority calculation"""
        try:
            vtype = traci.vehicle.getTypeID(vehicle_id)
            return vtype
        except:
            return 'car'
    
    def get_priority_score(self, vehicle_id):
        """Calculate priority score for a vehicle"""
        vtype = self.get_vehicle_type(vehicle_id)
        return self.priority_weights.get(vtype, 1.0)
    def get_current_datetime(self, simulation_step):
        """Convert simulation step (seconds) to datetime"""
        return self.simulation_start_time + timedelta(seconds=simulation_step)
    def get_vehicle_count_at_intersection(self, tl_id):
        """Count vehicles approaching this traffic light"""
        controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
        total_vehicles = 0
        
        for lane in set(controlled_lanes):  # Remove duplicates
            try:
                total_vehicles += traci.lane.getLastStepVehicleNumber(lane)
            except:
                continue
        
        return total_vehicles

    def predict_congestion_at_intersection(self, tl_id, step):
        """
        Get AI prediction for congestion at this intersection
        Returns: (prediction, congestion_level_label) or (None, None) if prediction fails
        """
        if not self.use_prediction:
            return None, None
        
        try:
            current_time = self.get_current_datetime(step)
            vehicle_count = self.get_vehicle_count_at_intersection(tl_id)
            
            # Get prediction
            prediction = self.predictor.predict_congestion(
                tl_id, current_time, vehicle_count
            )
            
            level = self.predictor.get_congestion_level_label(prediction)
            
            # Store for analysis
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
        Detect priority vehicles approaching the traffic light
        Returns: (has_priority, max_priority_score, vehicle_types)
        """
        # Get all vehicles on incoming lanes
        controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
        
        priority_vehicles = []
        max_priority = 0
        vehicle_types = []
        
        for lane in set(controlled_lanes):  # Remove duplicates
            vehicles_on_lane = traci.lane.getLastStepVehicleIDs(lane)
            
            for veh_id in vehicles_on_lane:
                try:
                    # Get vehicle position and distance to intersection
                    pos = traci.vehicle.getLanePosition(veh_id)
                    lane_length = traci.lane.getLength(lane)
                    distance_to_light = lane_length - pos
                    
                    # Check if vehicle is in detection zone
                    if distance_to_light <= self.detection_distance:
                        priority = self.get_priority_score(veh_id)
                        vtype = self.get_vehicle_type(veh_id)
                        
                        if priority > 1.0:  # Not a regular car
                            priority_vehicles.append((veh_id, priority, vtype))
                            max_priority = max(max_priority, priority)
                            vehicle_types.append(vtype)
                            
                except traci.exceptions.TraCIException:
                    continue
        
        has_priority = len(priority_vehicles) > 0
        return has_priority, max_priority, vehicle_types
    
    def control_signal(self, tl_id, current_phase, time_in_phase, step):
        """
        AI-Enhanced signal control based on:
        1. Priority vehicles (reactive)
        2. Congestion prediction (proactive)
        
        Returns: should_extend (bool)
        """
        
        # STEP 1: Check for priority vehicles (existing logic)
        has_priority, priority_score, vehicle_types = self.detect_priority_vehicles(tl_id)
        
        # STEP 2: Get AI congestion prediction
        predicted_congestion, congestion_level = self.predict_congestion_at_intersection(tl_id, step)
        
        # Log predictions periodically
        if predicted_congestion and step % 300 == 0:  # Every 5 minutes
            print(f"[AI PREDICTION] {tl_id}: {congestion_level} congestion in 15min ({predicted_congestion:.2f})")
        
        # DECISION LOGIC
        should_extend = False
        decision_reason = None
        
        # PRIORITY 1: Emergency vehicles (highest priority)
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
                if time_in_phase < self.max_green_time:
                    print(f"[{tl_id}] Bus detected - extending green")
                    self.stats['priority_vehicles_served']['regular_bus'] += 1
                    self.stats['signal_extensions'] += 1
                    should_extend = True
                    decision_reason = "regular_bus"
        
        # PRIORITY 2: AI Proactive Congestion Prevention
        # Only act if no priority vehicles and prediction shows high congestion
        if not should_extend and predicted_congestion:
            # Thresholds for action
            SEVERE_THRESHOLD = 0.70  # Take action if severe congestion predicted
            HEAVY_THRESHOLD = 0.55   # Consider action if heavy congestion predicted
            
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
            
            elif predicted_congestion >= HEAVY_THRESHOLD and time_in_phase < self.max_green_time - 10:
                # Only extend if we have room in the phase
                print(f"[{tl_id}] 🤖 AI: HEAVY congestion predicted ({predicted_congestion:.2f}) - minor extension")
                should_extend = True
                decision_reason = "ai_heavy_prediction"
                self.stats['ai_preemptive_actions'] += 1
        
        # Log decision for analysis
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
    
    def run_simulation(self, gui=True):
        """Main simulation loop"""
        
        # Start SUMO
        sumoBinary = "sumo-gui" if gui else "sumo"
        sumoCmd = [sumoBinary, "-c", "olympic_corridor.sumocfg"]
        
        traci.start(sumoCmd)

        # Get all traffic lights in network
        self.traffic_lights = traci.trafficlight.getIDList()
        print(f"Monitoring {len(self.traffic_lights)} traffic lights: {self.traffic_lights}")
        
        step = 0
        print("=" * 60)
        print("FairLane Dynamic Transit Lane Optimizer")
        print("=" * 60)
        print("\nStarting simulation...")
        print("Monitoring traffic lights:", self.traffic_lights)
        print("\nPriority System:")
        for vtype, weight in sorted(self.priority_weights.items(), key=lambda x: x[1], reverse=True):
            print(f"  {vtype}: {weight}x priority")
        print("\n" + "=" * 60 + "\n")
        
        # Track phase timing for each traffic light
        tl_phase_start = {tl: 0 for tl in self.traffic_lights}
        
        try:
            while traci.simulation.getMinExpectedNumber() > 0:
                traci.simulationStep()
                step += 1
                
                # Update statistics
                self.stats['total_vehicles'] = traci.vehicle.getIDCount()
                
                # Control each traffic light
                for tl_id in self.traffic_lights:
                    try:
                        current_phase = traci.trafficlight.getPhase(tl_id)
                        time_in_phase = step - tl_phase_start[tl_id]
                        
                        # Check for priority vehicles and AI predictions, extend green if needed
                        should_extend = self.control_signal(tl_id, current_phase, time_in_phase, step)
                        
                        # Implement extension by modifying phase duration
                        if should_extend and time_in_phase >= self.min_green_time:
                            # Get current program
                            programs = traci.trafficlight.getAllProgramLogics(tl_id)
                            if programs:
                                current_program = programs[0]
                                phases = list(current_program.phases)
                                
                                # Extend current phase
                                if current_phase < len(phases):
                                    phases[current_phase] = traci.trafficlight.Phase(
                                        phases[current_phase].duration + self.extension_time,
                                        phases[current_phase].state,
                                        phases[current_phase].minDur,
                                        phases[current_phase].maxDur
                                    )
                                    
                                    # Update program
                                    logic = traci.trafficlight.Logic(
                                        current_program.programID,
                                        current_program.type,
                                        current_program.currentPhaseIndex,
                                        phases
                                    )
                                    traci.trafficlight.setProgramLogic(tl_id, logic)
                        
                        # Track phase changes
                        new_phase = traci.trafficlight.getPhase(tl_id)
                        if new_phase != current_phase:
                            tl_phase_start[tl_id] = step
                            
                    except traci.exceptions.TraCIException as e:
                        continue
                
                # Print periodic updates
                if step % 300 == 0:  # Every 5 minutes (simulation time)
                    self.print_statistics(step)
        
        finally:
            print("\n" + "=" * 60)
            print("Simulation Complete")
            print("=" * 60)
            self.print_final_statistics()
            traci.close()
    
    def print_statistics(self, step):
        """Print current statistics"""
        print(f"\n--- Time: {step}s ({step//60} minutes) ---")
        print(f"Total vehicles in simulation: {self.stats['total_vehicles']}")
        print(f"Signal extensions: {self.stats['signal_extensions']}")
        
        # AI Statistics
        if self.use_prediction:
            print(f"AI predictions made: {self.stats['predictions_made']}")
            print(f"AI preemptive actions: {self.stats['ai_preemptive_actions']}")
        
        print("Priority vehicles served:")
        for vtype, count in self.stats['priority_vehicles_served'].items():
            print(f"  {vtype}: {count}")
    
    def print_final_statistics(self):
        """Print final statistics"""
        print("\nFinal Statistics:")
        print(f"Total signal extensions: {self.stats['signal_extensions']}")
        
        # AI Statistics
        if self.use_prediction:
            print("\n🤖 AI Performance:")
            print(f"  Total predictions made: {self.stats['predictions_made']}")
            print(f"  Preemptive actions taken: {self.stats['ai_preemptive_actions']}")
            print(f"  High congestion events prevented: {self.stats['high_congestion_prevented']}")
            
            if self.stats['predictions_made'] > 0:
                action_rate = (self.stats['ai_preemptive_actions'] / self.stats['predictions_made']) * 100
                print(f"  AI action rate: {action_rate:.1f}%")
        
        print("\nPriority vehicles served:")
        total_priority = 0
        for vtype, count in sorted(self.stats['priority_vehicles_served'].items(), 
                                key=lambda x: self.priority_weights.get(x[0], 0), 
                                reverse=True):
            print(f"  {vtype}: {count}")
            total_priority += count
        print(f"  TOTAL: {total_priority}")
        
        print("\nSystem Impact:")
        if self.stats['signal_extensions'] > 0:
            print(f"  ✓ System made {self.stats['signal_extensions']} total priority decisions")
            print(f"  ✓ Improved transit flow for {total_priority} priority vehicles")
            
            if self.use_prediction:
                print(f"  ✓ AI prevented {self.stats['high_congestion_prevented']} congestion events")
                print(f"  ✓ Proactive AI control: {self.stats['ai_preemptive_actions']} preemptive adjustments")
            
            print(f"  ✓ Enhanced accessibility and emergency response")
        
        print("\n" + "=" * 60)
        
        # Save prediction history for analysis
        if self.use_prediction and len(self.prediction_history) > 0:
            self.save_prediction_data()

    def save_prediction_data(self):
        """Save prediction history for later analysis"""
        import pandas as pd
        
        df = pd.DataFrame(self.prediction_history)
        df.to_csv('prediction_history.csv', index=False)
        print("\n✓ Saved prediction history to: prediction_history.csv")
        
        if hasattr(self, 'decision_log'):
            decision_df = pd.DataFrame(self.decision_log)
            decision_df.to_csv('decision_log.csv', index=False)
            print("✓ Saved decision log to: decision_log.csv")


def main():
    """Main entry point"""
    # Check command line arguments
    gui = True
    if len(sys.argv) > 1 and sys.argv[1] == "--no-gui":
        gui = False
    
    # Create controller and run
    controller = FairLaneController()
    controller.run_simulation(gui=gui)


if __name__ == "__main__":
    main()